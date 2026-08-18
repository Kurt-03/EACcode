"""3-layer context-overflow defense (Phase G.3, Plan G v5).

Mirrors Hermes' tools/tool_result_storage.py + tools/hook_output_spill.py.
Three independent defenses keep a single large tool result from
overflowing the model context:

  Layer 1: per-tool output cap - tools truncate their own output
            before returning (already in place via max_chars).

  Layer 2: per-result persistence - if a tool result exceeds the
            threshold, the full text is written to a temp dir under
            <data>/tool-results/<tool_call_id>.txt and the in-context
            payload is replaced with a preview + path. The model can
            read_file() the path to access the full content.

  Layer 3: per-turn aggregate budget - after all tool results for one
            assistant turn are collected, if the combined size exceeds
            MAX_TURN_BUDGET_CHARS, the largest non-persisted results are
            spilled to disk until the budget is met.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any


PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"

STORAGE_DIR_NAME = "tool-results"
HEREDOC_MARKER = "HERMES_PERSIST_EOF"
MAX_PREVIEW_CHARS = 800
MAX_TURN_BUDGET_CHARS = 200_000
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
_MAX_FILENAME_STEM = 120


def _storage_dir() -> Path:
    """Root for persisted tool results."""
    from eaccode import config as cfg

    try:
        return cfg.data_dir() / STORAGE_DIR_NAME
    except Exception:
        return Path.home() / ".local" / "share" / "eaccode" / STORAGE_DIR_NAME


def _safe_filename(tool_call_id: str) -> str:
    raw = str(tool_call_id or "tool")
    safe = _UNSAFE_FILENAME_CHARS.sub("-", raw)
    # Collapse "../" / ".." patterns to a single dash so the filename
    # never escapes its target directory.
    while ".." in safe:
        safe = safe.replace("..", "-")
    safe = safe.strip("-")
    if not safe:
        safe = uuid.uuid4().hex
    return safe[:_MAX_FILENAME_STEM]


def persist_tool_result(
    tool_name: str,
    tool_call_id: str,
    body: str,
) -> dict[str, Any]:
    """Write ``body`` to disk and return the metadata for the preview.

    Returns a dict with ``path``, ``preview``, ``size_chars``, and
    ``hash``. The caller is expected to substitute the preview into
    the model's tool-result message.
    """
    if not body:
        return {
            "path": None,
            "preview": "",
            "size_chars": 0,
            "hash": "",
        }
    storage = _storage_dir()
    storage.mkdir(parents=True, exist_ok=True)
    name = f"{tool_name}-{_safe_filename(tool_call_id)}-{uuid.uuid4().hex[:6]}.txt"
    full_path = storage / name
    full_path.write_text(body, encoding="utf-8", errors="replace")
    digest = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
    preview_body = body[:MAX_PREVIEW_CHARS]
    if len(body) > MAX_PREVIEW_CHARS:
        preview_body = preview_body.rstrip() + "…"
    return {
        "path": str(full_path),
        "preview": preview_body,
        "size_chars": len(body),
        "hash": digest,
    }


def maybe_persist_tool_result(
    tool_name: str,
    tool_call_id: str,
    body: str,
    *,
    threshold_chars: int = 16_000,
) -> tuple[str, dict[str, Any] | None]:
    """Persist if body exceeds threshold, else return body verbatim.

    Returns ``(in_context_body, metadata)``. The metadata is None when
    no persistence happened.
    """
    if len(body) <= threshold_chars:
        return body, None
    meta = persist_tool_result(tool_name, tool_call_id, body)
    preview_body = (
        f"{PERSISTED_OUTPUT_TAG}\n"
        f"path: {meta['path']}\n"
        f"size: {meta['size_chars']} chars (sha256: {meta['hash'][:12]}…)\n"
        f"preview ({MAX_PREVIEW_CHARS} chars):\n"
        f"{meta['preview']}\n"
        f"{PERSISTED_OUTPUT_CLOSING_TAG}\n"
    )
    return preview_body, meta


def enforce_turn_budget(
    tool_results: list[dict[str, Any]],
    *,
    max_chars: int = MAX_TURN_BUDGET_CHARS,
) -> list[dict[str, Any]]:
    """Spill the largest non-persisted results until the turn fits.

    Each ``tool_result`` is a dict with keys ``tool_call_id``,
    ``tool_name``, ``content``. If a result's content is already wrapped
    in ``<persisted-output>`` tags it counts as already-spilled and is
    skipped.
    """
    chars_per_result: list[int] = []
    for r in tool_results:
        content = str(r.get("content", ""))
        if PERSISTED_OUTPUT_TAG in content:
            chars_per_result.append(0)
            continue
        chars_per_result.append(len(content))

    total = sum(chars_per_result)
    if total <= max_chars:
        return tool_results

    # Spill the largest entries first until we fit.
    indexed = sorted(
        enumerate(tool_results),
        key=lambda kv: chars_per_result[kv[0]],
        reverse=True,
    )
    new_results: list[dict[str, Any]] = list(tool_results)
    for original_idx, result in indexed:
        if total <= max_chars:
            break
        if chars_per_result[original_idx] == 0:
            continue
        original_content = str(result.get("content", ""))
        spilled_body, _ = maybe_persist_tool_result(
            result.get("tool_name", "tool"),
            str(result.get("tool_call_id", "")),
            original_content,
            threshold_chars=0,
        )
        new_results[original_idx] = dict(result, content=spilled_body)
        chars_per_result[original_idx] = len(spilled_body)
        total = sum(chars_per_result)
    return new_results


__all__ = [
    "PERSISTED_OUTPUT_TAG",
    "PERSISTED_OUTPUT_CLOSING_TAG",
    "MAX_PREVIEW_CHARS",
    "MAX_TURN_BUDGET_CHARS",
    "persist_tool_result",
    "maybe_persist_tool_result",
    "enforce_turn_budget",
]
