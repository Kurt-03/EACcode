"""JSON-Schema sanitization for tool descriptions (Phase G.5, Plan G v5).

Some providers reject schemas with $ref, nullable unions, const, or
format-pattern hints. This module normalises schemas to a portable
subset before sending them to the model API.

Mirrors Hermes' tools/schema_sanitizer.py (T5 in Plan G v5).
"""

from __future__ import annotations

import re
from typing import Any


# Providers that can choke on advanced schema features.
_STRICT_PROVIDERS = frozenset(
    {
        "openai",     # historical, mostly fine now
        "deepseek",
        "xiaomi",
        "moonshot",
        "kimi",
        "minimax",    # MiniMax has had schema-validation issues historically
    }
)


def sanitize_property_key(key: str) -> str:
    """Return a portable property key.

    Some providers reject keys with characters outside
    ``[A-Za-z0-9_-]``. Replace dots, spaces and other punctuation.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", key)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def sanitize_tool_schemas(
    tools: list[dict[str, Any]],
    *,
    provider: str | None = None,
) -> list[dict[str, Any]]:
    """Return sanitised OpenAI-format tool schemas.

    Each schema is rewritten to drop $ref, strip top-level combinators,
    collapse nullable unions, drop const, drop pattern/format hints,
    and rename keys that contain illegal characters.
    """
    if not _should_sanitize(provider):
        return tools
    out: list[dict[str, Any]] = []
    for tool in tools:
        try:
            out.append(_sanitize_single_tool(tool))
        except Exception:
            # Best-effort: if sanitization explodes, return the original
            # and let the provider complain.
            out.append(tool)
    return out


def _should_sanitize(provider: str | None) -> bool:
    if not provider:
        return True
    return provider.lower().split("/", 1)[0] in _STRICT_PROVIDERS


def _sanitize_single_tool(tool: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(tool, dict):
        return tool
    fn = tool.get("function") or tool
    if not isinstance(fn, dict):
        return tool
    params = fn.get("parameters")
    if not isinstance(params, dict):
        return tool
    fn["parameters"] = _sanitize_schema(params, path="<tool>")
    return tool


def _sanitize_schema(node: Any, *, path: str) -> Any:
    if not isinstance(node, dict):
        return node
    # Drop $ref and $siblings at any level
    cleaned = {k: v for k, v in node.items() if not k.startswith("$")}
    # Recurse into known sub-schema keys
    for sub in ("properties", "patternProperties", "definitions"):
        sub_dict = cleaned.get(sub)
        if isinstance(sub_dict, dict):
            cleaned[sub] = {
                sanitize_property_key(k): _sanitize_schema(v, path=f"{path}.{sub}.{k}")
                for k, v in sub_dict.items()
            }
    for sub in ("items", "additionalProperties", "additionalItems", "contains", "if", "then", "else", "not"):
        sub_v = cleaned.get(sub)
        if isinstance(sub_v, dict):
            cleaned[sub] = _sanitize_schema(sub_v, path=f"{path}.{sub}")
    # Drop const, enum stays but stripped of advanced types
    if "const" in cleaned:
        del cleaned["const"]
    # Strip pattern/format hints (some providers reject)
    for k in ("pattern", "format", "minLength", "maxLength", "minimum", "maximum"):
        if k in cleaned:
            del cleaned[k]
    # Collapse ["x", "null"] type unions to plain type with nullable=true
    if isinstance(cleaned.get("type"), list):
        original_types = cleaned["type"]
        non_null = [t for t in original_types if t != "null"]
        if non_null:
            cleaned["type"] = non_null[0]
            if "null" in original_types:
                cleaned["nullable"] = True
    # Drop top-level oneOf/anyOf/allOf at tool-level (most providers don't
    # need them and some reject).
    if path == "<tool>":
        for k in ("oneOf", "anyOf", "allOf"):
            if k in cleaned:
                del cleaned[k]
    return cleaned
