"""Configurable tool-output truncation limits (Phase G.12, Plan G v5).

Mirrors Hermes' tools/tool_output_limits.py so power users can tune
truncation thresholds from config.yaml without patching the source.

Example config.yaml::

    tool_output:
      max_bytes: 100000      # read_file / tool-result cap (chars)
      max_lines: 5000       # read_file pagination + truncation cap
      max_line_length: 2000  # per-line length cap before '... [truncated]'

Behaviour is unchanged when the config key is absent (built-in
defaults).
"""

from __future__ import annotations

from typing import Any, Dict

# Hardcoded defaults - match the existing in-tool constants so adding
# this module is behaviour-preserving for users without a tool_output
# config block.
DEFAULT_MAX_BYTES = 50_000       # terminal/command-output cap (chars)
DEFAULT_MAX_LINES = 2000         # read_file pagination + truncation cap
DEFAULT_MAX_LINE_LENGTH = 2000   # per-line cap before truncation

# Module-level cache - populated on first call. Avoids repeated disk I/O
# on every tool call.
_cached_limits: dict[str, int] | None = None


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError):
        return default
    if iv <= 0:
        return default
    return iv


def get_tool_output_limits() -> Dict[str, int]:
    """Return resolved tool-output limits from config.

    Keys: max_bytes, max_lines, max_line_length. Missing or invalid
    entries fall through to DEFAULT_* constants. NEVER raises.

    Result is cached for the process lifetime. Call
    _reset_tool_output_limits_cache() in tests after config edits.
    """
    global _cached_limits
    if _cached_limits is not None:
        return _cached_limits
    section: dict[str, Any] = {}
    try:
        from eaccode import config as cfg

        loaded = cfg.load_config() or {}
        if isinstance(loaded, dict):
            sec = loaded.get("tool_output")
            if isinstance(sec, dict):
                section = sec
    except Exception:
        section = {}

    _cached_limits = {
        "max_bytes": _coerce_positive_int(section.get("max_bytes"), DEFAULT_MAX_BYTES),
        "max_lines": _coerce_positive_int(section.get("max_lines"), DEFAULT_MAX_LINES),
        "max_line_length": _coerce_positive_int(
            section.get("max_line_length"), DEFAULT_MAX_LINE_LENGTH
        ),
    }
    return _cached_limits


def _reset_tool_output_limits_cache() -> None:
    """Reset the cached limits (for tests / config hot-reload)."""
    global _cached_limits
    _cached_limits = None


def get_max_bytes() -> int:
    return get_tool_output_limits()["max_bytes"]


def get_max_lines() -> int:
    return get_tool_output_limits()["max_lines"]


def get_max_line_length() -> int:
    return get_tool_output_limits()["max_line_length"]
