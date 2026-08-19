"""Stream-chunk renderer (Plan K K.3).

Format StreamChunks for terminal output. Used by ``eaccode --verbose``
so the user sees tool calls inline with text.
"""

from __future__ import annotations

import json
from typing import Any

from eaccode.providers.base import StreamChunk


# Tool name -> icon (one char + name)
TOOL_ICONS = {
    "read_file": "📖",
    "write_file": "✏️",
    "file_edit": "✏️",
    "patch_file": "✏️",
    "patch_multiple": "✏️",
    "list_files": "📂",
    "search_files": "🔍",
    "repo_scan": "🔍",
    "repo_search": "🔍",
    "run_command": "⚙️",
    "spawn_subagent": "🧠",
    "http_get": "🌐",
    "web_search": "🔍",
    "create_skill": "📚",
    "improve_skill": "📚",
    "memory_add": "💾",
    "memory_remove": "💾",
    "todo_read": "☑️",
    "todo_write": "☑️",
}


def tool_icon(name: str) -> str:
    return TOOL_ICONS.get(name, "🔧")


# Args that contain secrets - replaced with ***REDACTED*** before display.
SECRET_KEYS = frozenset({
    "api_key", "apikey", "password", "secret", "token", "auth",
    "authorization", "private_key", "ssh_key",
})


def redact_secrets(args: dict[str, object]) -> dict[str, object]:
    """Replace values of secret-keyed args with ***REDACTED***."""
    out: dict[str, object] = {}
    for k, v in args.items():
        if any(s in k.lower() for s in SECRET_KEYS):
            out[k] = "***REDACTED***"
        else:
            out[k] = v
    return out


def _short(value: object, max_len: int = 80) -> str:
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def render_chunk(chunk: StreamChunk, verbose: bool = True) -> str | None:
    """Format a StreamChunk for terminal output. None = no output.

    Args:
        chunk: The chunk to render.
        verbose: When False, suppress tool_start/tool_end/tool_error events.
    """
    if chunk.kind == "text":
        return chunk.content
    if chunk.kind == "reasoning":
        return f"💭 {chunk.content}" if verbose else None

    if not verbose:
        return None

    if chunk.kind == "tool_start":
        icon = tool_icon(chunk.tool_name)
        safe_args = redact_secrets(chunk.tool_args)
        if safe_args:
            args_str = ", ".join(f"{k}={_short(v)!r}" for k, v in safe_args.items())
        else:
            args_str = ""
        return f"  {icon} {chunk.tool_name}({args_str})"

    if chunk.kind == "tool_end":
        icon = tool_icon(chunk.tool_name)
        result_short = _short(chunk.tool_result, max_len=120)
        return f"  ✓ {icon} {chunk.tool_name} ({chunk.tool_duration_ms}ms): {result_short}"

    if chunk.kind == "tool_error":
        icon = tool_icon(chunk.tool_name)
        return f"  ✗ {icon} {chunk.tool_name} ({chunk.tool_duration_ms}ms): {chunk.tool_error}"

    if chunk.kind == "tool_call":
        return f"  → {chunk.tool_call.name if chunk.tool_call else '?'}({_short(chunk.tool_call.arguments) if chunk.tool_call else ''})"

    if chunk.kind == "done":
        return None  # quiet

    if chunk.kind == "error":
        return f"  ✗ Error: {chunk.content}"

    return None


__all__ = [
    "TOOL_ICONS",
    "SECRET_KEYS",
    "tool_icon",
    "redact_secrets",
    "render_chunk",
]
