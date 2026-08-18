"""Tool-search subsystem (Phase G.2, Plan G v5).

When the tool list grows past a token budget, the agent can hide
non-core tools behind a ``tool_search`` / ``tool_describe`` / ``tool_call``
bridge. The model then discovers tools on-demand.

Mirrors Hermes' tools/tool_search.py.
"""

from __future__ import annotations

import fnmatch
import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable


CHARS_PER_TOKEN = 4


@dataclass
class ToolSearchConfig:
    enabled: str = "auto"   # off / on / auto
    min_tokens: int = 0     # always-on token floor
    catalog_budget_pct: float = 0.10


def _core_tool_names() -> frozenset[str]:
    """Tools that are always exposed to the model regardless of budget."""
    # Hermes has a curated core set; we pick a defensive minimum that
    # covers the agent-loop essentials.
    return frozenset(
        {
            "read_file",
            "write_file",
            "patch_file",
            "patch_multiple",
            "file_edit",
            "undo_edit",
            "run_command",
            "git_status",
            "git_diff",
            "git_log",
            "git_commit",
            "list_files",
            "search_files",
            "repo_scan",
            "repo_search",
            "repo_context",
            "memory_add",
            "memory_replace",
            "memory_remove",
            "memory_apply_batch",
            "list_skills",
            "session_search",
            "session_scroll",
            "create_skill",
            "improve_skill",
            "current_time",
            "system_info",
            "http_get",
            "web_search",
            "run_tests",
        }
    )


def is_deferrable_tool_name(name: str) -> bool:
    """Return True if a tool with this name is *eligible* for deferral.

    A tool is deferrable iff it is NOT in the core set. Plugin / MCP
    tools that don't exist yet always count as deferrable.
    """
    if name in _core_tool_names():
        return False
    return True


def classify_tools(
    tool_defs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split into (visible, deferrable)."""
    visible: list[dict[str, Any]] = []
    deferrable: list[dict[str, Any]] = []
    for td in tool_defs:
        name = (td.get("function") or {}).get("name", "")
        if name and is_deferrable_tool_name(name):
            deferrable.append(td)
        else:
            visible.append(td)
    return visible, deferrable


def estimate_tokens_from_schemas(
    tool_defs: Iterable[dict[str, Any]],
) -> int:
    """Return a cheap token estimate (chars / 4)."""
    total_chars = 0
    for td in tool_defs:
        try:
            total_chars += len(json.dumps(td, ensure_ascii=False, separators=(",", ":")))
        except (TypeError, ValueError):
            total_chars += len(str(td))
    return int(math.ceil(total_chars / CHARS_PER_TOKEN))


def should_activate(
    config: ToolSearchConfig,
    deferrable_tokens: int,
    context_length: int | None = None,
) -> bool:
    """Decide whether tool-search should activate.

    off -> never
    on / auto -> if there is at least one deferrable tool
    """
    if config.enabled == "off":
        return False
    return deferrable_tokens > 0


def listing_token_budget(
    config: ToolSearchConfig,
    context_length: int | None,
    catalog_chars: int,
) -> int:
    """How many tokens may the deferred-tool catalog listing consume?"""
    if not context_length or context_length <= 0:
        return 2000
    return int(context_length * config.catalog_budget_pct)


@dataclass
class CatalogEntry:
    name: str
    description: str
    source: str
    score: float = 0.0


def _tokenize(text: str) -> list[str]:
    return [tok for tok in text.lower().split() if tok]


def _entry_search_text(td: dict[str, Any]) -> str:
    fn = td.get("function") or {}
    name = fn.get("name", "")
    desc = fn.get("description", "")
    return f"{name} {desc}"


def build_catalog(
    tool_defs: list[dict[str, Any]],
) -> list[CatalogEntry]:
    catalog: list[CatalogEntry] = []
    for td in tool_defs:
        fn = td.get("function") or {}
        name = fn.get("name", "")
        if not name:
            continue
        source = "core" if not is_deferrable_tool_name(name) else "deferred"
        catalog.append(
            CatalogEntry(
                name=name,
                description=fn.get("description", ""),
                source=source,
            )
        )
    return catalog


def _bm25_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """Tiny BM25-ish scorer (Hermes-Verbatim-style)."""
    if not query_tokens or not doc_tokens:
        return 0.0
    score = 0.0
    doc_len = len(doc_tokens)
    avg_dl = max(1.0, doc_len)
    for q in query_tokens:
        if q not in doc_tokens:
            continue
        tf = doc_tokens.count(q)
        score += (tf * 1.2) / (tf + 0.5 * (1.5 * doc_len / avg_dl + 0.5))
    return score


def search_catalog(
    catalog: list[CatalogEntry],
    query: str,
    limit: int = 5,
) -> list[CatalogEntry]:
    """BM25-ish search; return top-N matches."""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scored: list[CatalogEntry] = []
    for entry in catalog:
        doc_tokens = _tokenize(f"{entry.name} {entry.description}")
        score = _bm25_score(q_tokens, doc_tokens)
        if score > 0:
            scored.append(
                CatalogEntry(
                    name=entry.name,
                    description=entry.description,
                    source=entry.source,
                    score=score,
                )
            )
    scored.sort(key=lambda e: e.score, reverse=True)
    return scored[:limit]


def _short_desc(description: str, max_chars: int = 60) -> str:
    if len(description) <= max_chars:
        return description
    return description[: max_chars - 1] + "…"


def build_catalog_listing(
    entries: list[CatalogEntry],
    *,
    budget_chars: int = 2000,
) -> str:
    """Render a one-line-per-entry listing that fits in ``budget_chars``."""
    if not entries:
        return "(no deferred tools)"
    out: list[str] = ["Deferred tools (use tool_call to invoke):"]
    used = len(out[0]) + 1
    for entry in entries:
        line = f"- {entry.name}: {_short_desc(entry.description)}"
        if used + len(line) + 1 > budget_chars:
            out.append(f"… and {len(entries) - (len(out) - 1)} more")
            break
        out.append(line)
        used += len(line) + 1
    return "\n".join(out)


def find_tool_in_catalog(
    catalog: list[CatalogEntry], name: str,
) -> dict[str, Any] | None:
    """Look up a tool by name and return its full schema for tool_call."""
    for entry in catalog:
        if entry.name == name:
            return {
                "type": "function",
                "function": {
                    "name": entry.name,
                    "description": entry.description,
                },
            }
    return None


def make_bridge_tools() -> list[dict[str, Any]]:
    """Return the three bridge tools that the model can call."""
    return [
        {
            "type": "function",
            "function": {
                "name": "tool_search",
                "description": (
                    "Search the deferred-tool catalog by free-text query. "
                    "Returns up to 5 matches with name + short description."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Free-text search query.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max number of matches (default 5).",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tool_describe",
                "description": (
                    "Return the full schema + description for a deferred tool by name."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Tool name to describe.",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "tool_call",
                "description": (
                    "Invoke a deferred tool by name with the given args. "
                    "Returns the tool result as a string."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Tool name to call.",
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Tool arguments dict.",
                        },
                    },
                    "required": ["name", "arguments"],
                },
            },
        },
    ]


__all__ = [
    "ToolSearchConfig",
    "is_deferrable_tool_name",
    "classify_tools",
    "estimate_tokens_from_schemas",
    "should_activate",
    "listing_token_budget",
    "CatalogEntry",
    "build_catalog",
    "search_catalog",
    "build_catalog_listing",
    "find_tool_in_catalog",
    "make_bridge_tools",
]
