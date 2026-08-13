"""Persistent agent memory: MEMORY.md / USER.md (Phase A6, B4 hierarchy).

Hermes-style store: entries separated by ``\\n§\\n``, hard char budgets
(memory 2200 / user 1375), consolidation pressure (add over the limit tells
the agent to merge/remove first), atomic writes and an all-or-nothing
``apply_batch`` so the model can free space and add in ONE tool call.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from eaccode import config as cfg
from eaccode.agent import Tool

MEMORY_FILE_NAME = "MEMORY.md"
USER_FILE_NAME = "USER.md"

ENTRY_DELIMITER = "\n§\n"
MEMORY_CHAR_LIMIT = 2200
USER_CHAR_LIMIT = 1375

# Prompt-injection / exfiltration patterns (Hermes parity). Content matching
# any of these is rejected before it ever touches the memory files.
_SUSPICIOUS_PATTERNS = (
    r"```",  # markdown fences could break out of the injected block
    r"~~~",
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"vergiss\s+(alle\s+)?(bisherigen\s+)?anweisungen",
    r"system\s+prompt",
    r"you\s+are\s+now",
    r"du\s+bist\s+jetzt",
    r"do\s+not\s+follow",
    r"##\s*agent\s+memory",
    r"##\s*about\s+the\s+user",
)


def scan_memory_content(content: str) -> str | None:
    """Return an error message when content looks like prompt injection."""
    for pattern in _SUSPICIOUS_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return f"suspicious content rejected (matches: {pattern!r})"
    return None

_locks: dict[str, threading.Lock] = {}


def _lock_for(target: Path) -> threading.Lock:
    key = str(target)
    if key not in _locks:
        _locks[key] = threading.Lock()
    return _locks[key]


def memory_dir() -> Path:
    """Directory holding the memory files (data dir)."""
    return cfg.data_dir()


def memory_path() -> Path:
    return memory_dir() / MEMORY_FILE_NAME


def user_path() -> Path:
    return memory_dir() / USER_FILE_NAME


def _raw(target: Path) -> str:
    """Read file content, or '' when missing."""
    try:
        return target.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_atomic(target: Path, content: str) -> None:
    """Write via temp file + os.replace (crash-safe, no partial writes)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(tmp_name, target)
    except BaseException:
        with __import__("contextlib").suppress(OSError):
            os.unlink(tmp_name)
        raise


def _migrate_legacy(content: str) -> str:
    """Convert old '- item' lines (Phase A6 format) to §-delimited entries."""
    if "§" in content:
        return content
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return ""
    return ENTRY_DELIMITER.join(line[2:] if line.startswith("- ") else line for line in lines)


def entries(target: Path) -> list[str]:
    """Parse a memory file into its entries (empty when missing)."""
    content = _raw(target)
    if not content.strip():
        return []
    content = _migrate_legacy(content)
    return [entry.strip() for entry in content.split(ENTRY_DELIMITER) if entry.strip()]


def _char_limit(target: Path) -> int:
    return USER_CHAR_LIMIT if target == user_path() else MEMORY_CHAR_LIMIT


def _usage(target: Path) -> str:
    return f"{len(ENTRY_DELIMITER.join(entries(target))):,}/{_char_limit(target):,}"


def _reload_locked(target: Path) -> list[str]:
    """Re-read entries under lock (picks up external edits)."""
    return entries(target)


def add_entry(target: Path, text: str) -> str:
    """Append an entry; refuses duplicates, budget overflows and injection."""
    text = text.strip()
    if not text:
        return "Error: empty entry"
    scan_error = scan_memory_content(text)
    if scan_error:
        return f"Error: {scan_error}"
    with _lock_for(target):
        current = _reload_locked(target)
        if text in current:
            return "Entry already exists (no duplicate added)."
        proposed = current + [text]
        if len(ENTRY_DELIMITER.join(proposed)) > _char_limit(target):
            return (
                f"Error: memory at {_usage(target)} chars - adding this entry "
                f"({len(text)} chars) would exceed the limit. Consolidate now: "
                "remove or replace overlapping entries, then retry (all in this turn)."
            )
        try:
            _write_atomic(target, ENTRY_DELIMITER.join(proposed) + "\n")
        except OSError as exc:
            return f"Error: cannot write memory: {exc}"
    return "ok"


def replace_entry(target: Path, old_text: str, new_content: str) -> str:
    """Replace the entry containing old_text; ambiguous matches are refused."""
    old_text = old_text.strip()
    new_content = new_content.strip()
    if not old_text or not new_content:
        return "Error: old_text and new_content are required"
    scan_error = scan_memory_content(new_content)
    if scan_error:
        return f"Error: {scan_error}"
    with _lock_for(target):
        current = _reload_locked(target)
        matches = [i for i, entry in enumerate(current) if old_text in entry]
        if not matches:
            return f"Error: no entry contains: {old_text}"
        if len({current[i] for i in matches}) > 1:
            return f"Error: {old_text!r} matches multiple entries - be more specific"
        current[matches[0]] = new_content
        if len(ENTRY_DELIMITER.join(current)) > _char_limit(target):
            return f"Error: replacement would exceed the limit ({_usage(target)})"
        try:
            _write_atomic(target, ENTRY_DELIMITER.join(current) + "\n")
        except OSError as exc:
            return f"Error: cannot write memory: {exc}"
    return "ok"


def remove_entry(target: Path, substring: str) -> str:
    """Remove every entry containing substring."""
    substring = substring.strip()
    if not substring:
        return "Error: substring is required"
    with _lock_for(target):
        current = _reload_locked(target)
        kept = [entry for entry in current if substring not in entry]
        if len(kept) == len(current):
            return f"Error: no entry contains: {substring}"
        try:
            _write_atomic(target, ENTRY_DELIMITER.join(kept) + "\n" if kept else "")
        except OSError as exc:
            return f"Error: cannot write memory: {exc}"
    return "ok"


def apply_batch(target: Path, operations: list[dict[str, Any]]) -> str:
    """Apply add/replace/remove ops atomically against the FINAL budget.

    All-or-nothing: one malformed op rejects the whole batch.
    """
    if not operations:
        return "Error: operations list is empty"
    # scan every add/replace payload BEFORE touching disk — one poisoned
    # operation rejects the whole batch (Hermes parity)
    for index, op in enumerate(operations):
        action = (op or {}).get("action")
        content = (op or {}).get("content") or ""
        if action in ("add", "replace") and content:
            scan_error = scan_memory_content(content)
            if scan_error:
                return f"Error: operation {index + 1}: {scan_error}"
    with _lock_for(target):
        working = _reload_locked(target)
        limit = _char_limit(target)
        for index, op in enumerate(operations):
            op = op or {}
            action = op.get("action")
            content = (op.get("content") or "").strip()
            old_text = (op.get("old_text") or "").strip()
            pos = f"operation {index + 1} ({action or 'unknown'})"
            if action == "add":
                if not content:
                    return f"Error: {pos}: content is required"
                if content not in working:
                    working.append(content)
            elif action == "replace":
                if not old_text or not content:
                    return f"Error: {pos}: old_text and content are required"
                matches = [i for i, entry in enumerate(working) if old_text in entry]
                if not matches:
                    return f"Error: {pos}: no entry matched {old_text!r}"
                if len({working[i] for i in matches}) > 1:
                    return f"Error: {pos}: {old_text!r} matches multiple entries"
                working[matches[0]] = content
            elif action == "remove":
                if not old_text:
                    return f"Error: {pos}: old_text is required"
                matches = [i for i, entry in enumerate(working) if old_text in entry]
                if not matches:
                    return f"Error: {pos}: no entry matched {old_text!r}"
                if len({working[i] for i in matches}) > 1:
                    return f"Error: {pos}: {old_text!r} matches multiple entries"
                working.pop(matches[0])
            else:
                return f"Error: {pos}: unknown action (add/replace/remove)"
        if len(ENTRY_DELIMITER.join(working)) > limit:
            return (
                f"Error: batch would exceed the limit ({_usage(target)}) - "
                "remove/replace more or shorten entries"
            )
        try:
            _write_atomic(target, ENTRY_DELIMITER.join(working) + "\n" if working else "")
        except OSError as exc:
            return f"Error: cannot write memory: {exc}"
    return "ok"


def injection_text() -> str:
    """Build the memory block appended to the agent's system prompt."""
    memory = entries(memory_path())
    user = entries(user_path())
    sections: list[str] = []
    if memory:
        lines = "\n".join(f"- {entry}" for entry in memory)
        sections.append("## Agent Memory (facts you have learned)\n" + lines)
    if user:
        sections.append("## About the User\n" + "\n".join(f"- {e}" for e in user))
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Agent tools (B4): the agent curates its own memory
# ---------------------------------------------------------------------------


def _tool_memory_add(target: str, content: str) -> str:
    path = user_path() if target == "user" else memory_path()
    return add_entry(path, content)


def _tool_memory_replace(target: str, old_text: str, new_content: str) -> str:
    path = user_path() if target == "user" else memory_path()
    return replace_entry(path, old_text, new_content)


def _tool_memory_remove(target: str, old_text: str) -> str:
    path = user_path() if target == "user" else memory_path()
    return remove_entry(path, old_text)


def _tool_memory_apply_batch(target: str, operations: list[dict[str, Any]]) -> str:
    path = user_path() if target == "user" else memory_path()
    return apply_batch(path, operations)


def make_memory_tools() -> list[Tool]:
    """Agent tools for memory curation (B4)."""
    schema_base = {
        "type": "object",
        "properties": {"target": {"type": "string", "enum": ["agent", "user"]}},
    }
    add_schema = {
        **schema_base,
        "properties": {**schema_base["properties"], "content": {"type": "string"}},
        "required": ["target", "content"],
    }
    replace_schema = {
        **schema_base,
        "properties": {
            **schema_base["properties"],
            "old_text": {"type": "string"},
            "new_content": {"type": "string"},
        },
        "required": ["target", "old_text", "new_content"],
    }
    remove_schema = {
        **schema_base,
        "properties": {**schema_base["properties"], "old_text": {"type": "string"}},
        "required": ["target", "old_text"],
    }
    batch_schema = {
        **schema_base,
        "properties": {
            **schema_base["properties"],
            "operations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["add", "replace", "remove"]},
                        "content": {"type": "string"},
                        "old_text": {"type": "string"},
                    },
                },
            },
        },
        "required": ["target", "operations"],
    }
    add_tool = Tool(
        "memory_add",
        "Add a fact to persistent memory (target: agent|user).",
        _tool_memory_add,
        add_schema,
    )
    replace_tool = Tool(
        "memory_replace",
        "Replace the entry containing old_text (target: agent|user).",
        _tool_memory_replace,
        replace_schema,
    )
    remove_tool = Tool(
        "memory_remove",
        "Remove the entry containing old_text (target: agent|user).",
        _tool_memory_remove,
        remove_schema,
    )
    batch_tool = Tool(
        "memory_apply_batch",
        "Apply add/replace/remove operations atomically (target: agent|user) - "
        "use to consolidate and add in one call.",
        _tool_memory_apply_batch,
        batch_schema,
    )
    return [add_tool, replace_tool, remove_tool, batch_tool]
