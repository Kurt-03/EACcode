"""Todo tool (Plan I P1.5).

A persistent todo list the model maintains across turns. Model-facing
tools are ``todo_write`` (replace the list) and ``todo_read`` (read
the current list). State lives at
``~/.local/share/eaccode/todos/<session_id>.json`` so it survives
across turns and across REPL sessions.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


TODO_STATUSES = ("pending", "in_progress", "completed", "cancelled")


@dataclass
class TodoItem:
    id: str
    content: str
    status: str  # one of TODO_STATUSES
    note: str = ""

    def __post_init__(self) -> None:
        if self.status not in TODO_STATUSES:
            raise ValueError(
                f"invalid status {self.status!r} (expected one of {TODO_STATUSES})"
            )


def todo_file(session_id: str) -> Path:
    """Return the path to the todo-list file for ``session_id``."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "eaccode" / "todos" / f"{session_id}.json"
    return Path.home() / ".local" / "share" / "eaccode" / "todos" / f"{session_id}.json"


_write_lock = threading.Lock()

# Per-session state (Plan J thread-safety).
_active_sessions: dict[str, str] = {}
DEFAULT_TODO_SESSION_KEY = "default"


def _todo_key(session_id: str | None) -> str:
    """Resolve a session_id for the dict lookup."""
    return str(session_id or DEFAULT_TODO_SESSION_KEY)


def read_todos(session_id: str) -> list[TodoItem]:
    """Return the persisted todo list, or empty list when none."""
    path = todo_file(session_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[TodoItem] = []
    for entry in data or []:
        if not isinstance(entry, dict):
            continue
        try:
            out.append(TodoItem(
                id=str(entry.get("id", "")),
                content=str(entry.get("content", "")),
                status=str(entry.get("status", "pending")),
                note=str(entry.get("note", "")),
            ))
        except ValueError:
            continue
    return out


def write_todos(session_id: str, items: list[TodoItem]) -> None:
    """Replace the persisted todo list atomically."""
    path = todo_file(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=".todos.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump([asdict(it) for it in items], fh, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def clear_todos(session_id: str) -> None:
    """Remove the todo file."""
    path = todo_file(session_id)
    if path.exists():
        path.unlink()


# -- Tool-call functions (callable by Agent) --------------------------------

def _resolve_active_session(session_id: str | None) -> str | None:
    """Return the explicit session_id, else the per-thread active one."""
    if session_id:
        return session_id
    return _active_sessions.get(_todo_key(None))


def set_active_session(session_id: Optional[str]) -> None:
    """Set the session-id used by todo_read/todo_write (for this thread)."""
    _active_sessions[_todo_key(None)] = session_id


def get_active_session() -> Optional[str]:
    return _active_sessions.get(_todo_key(None))


def todo_write(items: list[dict], session_id: str | None = None) -> str:
    """Replace the current todo list.

    Each item: ``{"id": ..., "content": ..., "status": ..., "note": ...}``
    """
    sid = session_id or _active_sessions.get(_todo_key(None))
    if not sid:
        return "Error: no active session"
    parsed: list[TodoItem] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        try:
            parsed.append(TodoItem(
                id=str(entry.get("id", "")),
                content=str(entry.get("content", "")),
                status=str(entry.get("status", "pending")),
                note=str(entry.get("note", "")),
            ))
        except ValueError as exc:
            return f"Error: {exc}"
    write_todos(sid, parsed)
    return f"wrote {len(parsed)} todos"


def todo_read(session_id: str | None = None) -> str:
    """Return the current todo list as a formatted string."""
    sid = session_id or _active_sessions.get(_todo_key(None))
    if not sid:
        return "Error: no active session"
    items = read_todos(sid)
    if not items:
        return "(no todos)"
    lines = []
    for it in items:
        marker = {
            "pending": "[ ]",
            "in_progress": "[*]",
            "completed": "[x]",
            "cancelled": "[-]",
        }[it.status]
        line = f"{marker} {it.id} {it.content}"
        if it.note:
            line += f"  // {it.note}"
        lines.append(line)
    return "\n".join(lines)


__all__ = [
    "TODO_STATUSES",
    "TodoItem",
    "todo_file",
    "read_todos",
    "write_todos",
    "clear_todos",
    "set_active_session",
    "get_active_session",
    "todo_write",
    "todo_read",
]