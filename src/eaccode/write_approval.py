"""Stage-approval for memory and skills writes (Plan H.minimal v4 Stufe 2).

Hermes-Verbatim analog of ``tools/write_approval.py`` (494 LOC).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


STAGED_SUBSYSTEMS = ("memory", "skills")


def pending_dir(subsystem: str) -> Path:
    """Return the directory where pending writes for ``subsystem`` live."""
    if subsystem not in STAGED_SUBSYSTEMS:
        raise ValueError(f"unknown subsystem {subsystem!r}")
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "eaccode" / "pending" / subsystem
    return Path.home() / ".local" / "share" / "eaccode" / "pending" / subsystem


@dataclass
class PendingWrite:
    """A staged write awaiting user approval."""

    id: str
    subsystem: str
    action: str
    summary: str
    origin: str
    created_at: float
    payload: dict[str, Any]


def _check_subsystem(subsystem: str) -> None:
    if subsystem not in STAGED_SUBSYSTEMS:
        raise ValueError(f"unknown subsystem {subsystem!r}")


def _resolve_pending_dir(subsystem: str) -> Path:
    """Resolve pending_dir at call-time so monkeypatch works.

    Uses ``sys.modules[__name__].pending_dir`` so tests can override the
    module-level ``pending_dir`` symbol and have the change propagate.
    """
    import sys as _sys

    fn = getattr(_sys.modules[__name__], "pending_dir")
    return fn(subsystem)


def stage_write(
    subsystem: str,
    payload: dict[str, Any],
    *,
    summary: str,
    origin: str = "foreground",
) -> PendingWrite:
    """Persist a pending write and return its record."""
    _check_subsystem(subsystem)
    pid = uuid.uuid4().hex[:8]
    pw = PendingWrite(
        id=pid,
        subsystem=subsystem,
        action=str(payload.get("action", "")),
        summary=(summary or "").strip(),
        origin=origin or "foreground",
        created_at=time.time(),
        payload=payload,
    )
    try:
        d = _resolve_pending_dir(subsystem)
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{pid}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(pw), ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
    return pw


def list_pending(subsystem: str) -> list[PendingWrite]:
    """Return all pending writes for ``subsystem``, newest-first."""
    _check_subsystem(subsystem)
    d = _resolve_pending_dir(subsystem)
    if not d.exists():
        return []
    out: list[PendingWrite] = []
    for path in d.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append(PendingWrite(
                id=str(data.get("id", path.stem)),
                subsystem=str(data.get("subsystem", subsystem)),
                action=str(data.get("action", "")),
                summary=str(data.get("summary", "")),
                origin=str(data.get("origin", "foreground")),
                created_at=float(data.get("created_at", 0)),
                payload=dict(data.get("payload", {})),
            ))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    out.sort(key=lambda w: w.created_at, reverse=True)
    return out


def get_pending(subsystem: str, pid: str) -> Optional[PendingWrite]:
    """Return a single pending write by id, or None."""
    for w in list_pending(subsystem):
        if w.id == pid:
            return w
    return None


def discard_pending(subsystem: str, pid: str) -> bool:
    """Remove a pending write. Returns True if removed."""
    _check_subsystem(subsystem)
    path = _resolve_pending_dir(subsystem) / f"{pid}.json"
    try:
        path.unlink()
        return True
    except OSError:
        return False


def pending_count(subsystem: str) -> int:
    """Count pending writes for ``subsystem``."""
    _check_subsystem(subsystem)
    d = _resolve_pending_dir(subsystem)
    if not d.exists():
        return 0
    return sum(1 for _ in d.glob("*.json"))


def clear_pending(subsystem: str) -> int:
    """Remove all pending writes for ``subsystem``."""
    _check_subsystem(subsystem)
    d = _resolve_pending_dir(subsystem)
    if not d.exists():
        return 0
    removed = 0
    for path in d.glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed


__all__ = [
    "PendingWrite",
    "STAGED_SUBSYSTEMS",
    "pending_dir",
    "stage_write",
    "list_pending",
    "get_pending",
    "discard_pending",
    "pending_count",
    "clear_pending",
]