"""Diff preview + persistent undo (Plan I P1.7).

Two features in one module:

1. ``format_diff_preview(old_content, new_content, path)`` returns
   a unified-diff-style preview so the agent can show the user what
   a write would change before the user approves it.

2. Persistent undo snapshots: every write tool captures a snapshot
   of the pre-write content at
   ``~/.local/share/eaccode/undo/<session>/<timestamp>--<path>.json``
   so users can ``/undo`` (or ``/undo all``) and recover previous
   versions across sessions.
"""

from __future__ import annotations

import difflib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


_WRITE_LOCK = threading.Lock()


def format_diff_preview(
    old_content: str,
    new_content: str,
    path: str = "",
    max_lines: int = 200,
) -> str:
    """Return a unified-diff-style preview of the change.

    Output starts with ``--- `` / ``+++ `` headers (Hermes-style)
    so it parses well in TUI rendering.
    """
    if old_content == new_content:
        return "(no changes)"
    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{path}" if path else "a",
        tofile=f"b/{path}" if path else "b",
        lineterm="",
    )
    lines = list(diff)
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines truncated)"]
    return "\n".join(lines)


# -- Persistent undo snapshots ------------------------------------------

def undo_dir(session_id: str) -> Path:
    """Return the directory where undo snapshots live."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "eaccode" / "undo" / session_id
    return Path.home() / ".local" / "share" / "eaccode" / "undo" / session_id


@dataclass
class UndoSnapshot:
    """A captured pre-write content, ready for restore."""

    timestamp: str
    path: str
    old_content: str | None  # None = file was new
    session_id: str

    @property
    def file_path(self) -> Path:
        safe_name = self.path.replace("/", "__").replace("\\", "__").replace(":", "_")
        ts = self.timestamp.replace(":", "-").replace(".", "-")
        return undo_dir(self.session_id) / f"{ts}__{safe_name}.json"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "path": self.path,
            "old_content": self.old_content,
            "session_id": self.session_id,
        }


def save_snapshot(
    session_id: str,
    path: str,
    old_content: str | None,
) -> UndoSnapshot:
    """Capture a snapshot of ``path`` before overwriting it.

    ``old_content`` is the pre-write content (None when the file was new).
    Returns the snapshot record (also persisted atomically).
    """
    snap = UndoSnapshot(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        path=path,
        old_content=old_content,
        session_id=session_id,
    )
    target = snap.file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        fd, tmp = tempfile.mkstemp(
            dir=str(target.parent),
            prefix=".undo.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(snap.to_dict(), fh, ensure_ascii=False)
            os.replace(tmp, target)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    return snap


def list_snapshots(session_id: str, path: str | None = None) -> list[UndoSnapshot]:
    """Return snapshots, newest-first. Optional filter by path."""
    d = undo_dir(session_id)
    if not d.exists():
        return []
    out: list[UndoSnapshot] = []
    for f in sorted(d.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if path is not None and data.get("path") != path:
            continue
        out.append(UndoSnapshot(
            timestamp=str(data.get("timestamp", "")),
            path=str(data.get("path", "")),
            old_content=data.get("old_content"),
            session_id=str(data.get("session_id", session_id)),
        ))
    return out


def restore_snapshot(snap: UndoSnapshot) -> bool:
    """Restore the file from ``snap.old_content``.

    Returns True if restored. If the original was None (file was new),
    the restored file is deleted (or not re-created).
    """
    target = Path(snap.path)
    if snap.old_content is None:
        # Original was non-existent: deleting is the "restore"
        if target.exists():
            target.unlink()
            return True
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(snap.old_content, encoding="utf-8")
    return True


def discard_snapshot(snap: UndoSnapshot) -> bool:
    """Delete a snapshot file (it has been used)."""
    try:
        snap.file_path.unlink()
        return True
    except OSError:
        return False


def clear_snapshots(session_id: str) -> int:
    """Remove all undo snapshots for the given session."""
    d = undo_dir(session_id)
    if not d.exists():
        return 0
    removed = 0
    for f in d.glob("*.json"):
        try:
            f.unlink()
            removed += 1
        except OSError:
            pass
    return removed


__all__ = [
    "format_diff_preview",
    "UndoSnapshot",
    "undo_dir",
    "save_snapshot",
    "list_snapshots",
    "restore_snapshot",
    "discard_snapshot",
    "clear_snapshots",
]