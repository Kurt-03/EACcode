"""Persistent blocked-pattern list (Phase C.8).

When the user picks "deny_always" for a call, the pattern is stored here
on disk so it survives eaccode restarts. Patterns are matched against the
full call text (tool_name + json args, like PermissionManager.call_text).

File: ~/.local/share/eaccode/blocked.json (schema-versioned).

08-18: deep permissions hardening (Plan C).
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_FILE_VERSION = 1
_LOCK = threading.Lock()


class BlockedPatternsStore:
    """Persists deny_always rules across eaccode restarts."""

    def __init__(self, path: Path | None = None) -> None:
        from eaccode import config as cfg

        if path is None:
            try:
                path = cfg.data_dir() / "blocked.json"
            except Exception:
                path = Path.home() / ".local" / "share" / "eaccode" / "blocked.json"
        self._path = path

    def _load(self) -> dict:
        if not self._path.exists():
            return {"version": _FILE_VERSION, "blocked": []}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"version": _FILE_VERSION, "blocked": []}
            data.setdefault("version", _FILE_VERSION)
            data.setdefault("blocked", [])
            return data
        except Exception:
            return {"version": _FILE_VERSION, "blocked": []}

    def _save(self, data: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def list(self) -> list[dict[str, Any]]:
        """Return all blocked patterns as a list."""
        with _LOCK:
            return list(self._load().get("blocked", []))

    def add(
        self,
        pattern: str,
        reason: str,
        tool_name: str = "",
    ) -> str:
        """Add a pattern. Returns the pattern's id."""
        with _LOCK:
            data = self._load()
            entry_id = uuid.uuid4().hex[:8]
            data["blocked"].append(
                {
                    "id": entry_id,
                    "pattern": pattern,
                    "reason": reason,
                    "tool": tool_name,
                    "added": datetime.now(timezone.utc).isoformat(),
                }
            )
            self._save(data)
            return entry_id

    def remove(self, entry_id: str) -> bool:
        """Remove by id. Returns True if removed."""
        with _LOCK:
            data = self._load()
            before = len(data["blocked"])
            data["blocked"] = [
                entry for entry in data["blocked"] if entry.get("id") != entry_id
            ]
            if len(data["blocked"]) == before:
                return False
            self._save(data)
            return True

    def matches(self, call_text: str) -> dict | None:
        """Return matching entry if any pattern in the store matches the call."""
        for entry in self.list():
            pattern = entry.get("pattern", "")
            if not pattern:
                continue
            try:
                if re.search(pattern, call_text, re.IGNORECASE):
                    return entry
            except re.error:
                continue
        return None


# Module-level default instance
_default = BlockedPatternsStore()


def list_blocked() -> list[dict[str, Any]]:
    return _default.list()


def add_blocked(pattern: str, reason: str, tool_name: str = "") -> str:
    return _default.add(pattern, reason, tool_name)


def remove_blocked(entry_id: str) -> bool:
    return _default.remove(entry_id)


def find_blocked(call_text: str) -> dict | None:
    return _default.matches(call_text)
