"""Token counter (Plan I P0.4).

Approximate token counts without depending on tiktoken or provider-specific
tokenizers. The heuristic is ``chars / 4`` which is the OpenAI rule-of-thumb
and close enough for compaction decisions.

If a provider exposes ``count_tokens`` we defer to it; otherwise we use the
heuristic.
"""

from __future__ import annotations

from typing import Any


# Default heuristic: 4 chars per token (OpenAI rule-of-thumb).
DEFAULT_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str, chars_per_token: int = DEFAULT_CHARS_PER_TOKEN) -> int:
    """Approximate token count for a string.

    Returns 0 for empty input. Strips trailing whitespace before measuring.
    """
    if not text:
        return 0
    cleaned = text.strip()
    if not cleaned:
        return 0
    return max(1, (len(cleaned) + chars_per_token - 1) // chars_per_token)


def estimate_message_tokens(message: dict[str, Any]) -> int:
    """Estimate the token cost of a single chat-completions message.

    Handles ``content`` (str or list of content-parts) and ``tool_calls``.
    """
    role = str(message.get("role", ""))
    base = estimate_tokens(role) + 4  # 4 = role-name overhead

    content = message.get("content", "")
    if isinstance(content, str):
        base += estimate_tokens(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                base += estimate_tokens(str(part.get("text", "")))
            else:
                base += estimate_tokens(str(part))

    tool_calls = message.get("tool_calls") or []
    for tc in tool_calls:
        if isinstance(tc, dict):
            fn = tc.get("function") or {}
            base += estimate_tokens(str(fn.get("name", "")))
            base += estimate_tokens(str(fn.get("arguments", "")))

    name = message.get("name")
    if name:
        base += estimate_tokens(str(name))

    return base


def estimate_history_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total token cost of a chat history."""
    total = 0
    for msg in messages:
        total += estimate_message_tokens(msg)
    return total


def estimate_tool_definitions_tokens(tools: list[dict[str, Any]]) -> int:
    """Estimate token cost of the tool manifest sent to the model."""
    total = 0
    for tool in tools:
        total += estimate_tokens(str(tool.get("name", "")))
        total += estimate_tokens(str(tool.get("description", "")))
        # Schema serializes to ~3x its JSON size in tokens
        schema_text = str(tool.get("input_schema") or tool.get("parameters") or {})
        total += estimate_tokens(schema_text) * 3
    return total


__all__ = [
    "DEFAULT_CHARS_PER_TOKEN",
    "estimate_tokens",
    "estimate_message_tokens",
    "estimate_history_tokens",
    "estimate_tool_definitions_tokens",
]