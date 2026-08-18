"""Sub-agent live transcript (Phase G.7, Plan G v5).

Hermes writes every sub-agent run to a per-run transcript file under
``~/.local/share/eaccode/live-transcripts/<delegation_id>/...txt``. The
transcript is appended to as the run progresses and is rendered live in
the REPL. This module implements that pattern in eaccode.

Mirrors tools/delegation_live_log.py in Hermes.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


LIVE_RETENTION_DAYS = 7
_TRANSCRIPT_LOCK = threading.Lock()


def live_transcript_root() -> Path:
    """Root directory for live transcripts."""
    from eaccode import config as cfg

    try:
        return cfg.data_dir() / "live-transcripts"
    except Exception:
        return Path.home() / ".local" / "share" / "eaccode" / "live-transcripts"


def new_live_delegation_id() -> str:
    """Return a fresh delegation id (timestamp + uuid suffix)."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    return f"sub-{ts}-{uuid.uuid4().hex[:8]}"


def _one_line(text: Any, limit: int = 240) -> str:
    """Flatten text to a single line, capped to ``limit`` characters."""
    if text is None:
        return ""
    s = str(text)
    s = s.replace("\r\n", "\n").replace("\n", "\\n")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        s = s[: limit - 1] + "…"
    return s


_SENSITIVE_PATTERNS = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "sk-ant-***"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-***"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_***"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9]{10,}"), "xox*-***"),
]


def redact(text: str) -> str:
    """Replace common secret patterns with a placeholder."""
    if not text:
        return text
    out = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


@dataclass
class LiveTranscriptWriter:
    """Append-only live transcript writer."""

    delegation_id: str
    tool_name: str
    manifest: list[dict[str, Any]] = field(default_factory=list)
    _closed: bool = False

    @property
    def path(self) -> Path:
        return _transcript_file(self.delegation_id)

    def log(self, message: str, **fields: Any) -> None:
        """Append one line to the transcript."""
        if self._closed:
            return
        # Make sure the directory exists even if no prior log() ran.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%H:%M:%S")
        flat_msg = _one_line(redact(message))
        extra = " ".join(f"{k}={_one_line(v)}" for k, v in fields.items())
        line = f"{ts} [{self.tool_name}] {flat_msg}"
        if extra:
            line += " " + extra
        with _TRANSCRIPT_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def update_manifest(self, status: str) -> None:
        """Update the manifest entry for this delegation."""
        with _TRANSCRIPT_LOCK:
            manifest_path = _manifest_path(self.delegation_id)
            data = {"delegation_id": self.delegation_id, "status": status}
            manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def close(self) -> None:
        self._closed = True


def _delegation_dir(delegation_id: str) -> Path:
    return live_transcript_root() / delegation_id


def _transcript_file(delegation_id: str) -> Path:
    return _delegation_dir(delegation_id) / "transcript.txt"


def _manifest_path(delegation_id: str) -> Path:
    return _delegation_dir(delegation_id) / "manifest.json"


def wrap_progress_callback(
    inner_cb: Callable[[str], None] | None,
    writer: LiveTranscriptWriter,
) -> Callable[[str], None]:
    """Wrap an existing progress callback so updates also hit the writer."""

    def wrapper(line: str) -> None:
        writer.log(line)
        if inner_cb is not None:
            try:
                inner_cb(line)
            except Exception:
                pass

    return wrapper


def create_live_transcripts(delegation_id: str, tool_name: str) -> tuple[LiveTranscriptWriter, Callable[[str], None]]:
    """Create a writer and matching callback in one call."""
    writer = LiveTranscriptWriter(delegation_id=delegation_id, tool_name=tool_name)
    writer.log(f"start: {tool_name}")
    callback = wrap_progress_callback(None, writer)
    return writer, callback


def update_manifest_status(delegation_id: str, status: str) -> None:
    """Update the manifest status without holding a writer reference."""
    path = _manifest_path(delegation_id)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}
    data["status"] = status
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def prune_stale_live_dirs(max_age_days: int = LIVE_RETENTION_DAYS) -> int:
    """Delete transcript dirs older than ``max_age_days``. Returns count removed."""
    root = live_transcript_root()
    if not root.exists():
        return 0
    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            continue
        if mtime < cutoff:
            try:
                for child in entry.rglob("*"):
                    if child.is_file():
                        child.unlink()
                for child in sorted(entry.rglob("*"), reverse=True):
                    if child.is_dir():
                        child.rmdir()
                entry.rmdir()
                removed += 1
            except OSError:
                pass
    return removed


__all__ = [
    "LiveTranscriptWriter",
    "live_transcript_root",
    "new_live_delegation_id",
    "create_live_transcripts",
    "wrap_progress_callback",
    "update_manifest_status",
    "prune_stale_live_dirs",
    "redact",
]
