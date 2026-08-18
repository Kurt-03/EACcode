"""Persistent storage for /approvals rules (Plan H.minimal v4, Tag 3).

Always-scoped rules are persisted across sessions to
``~/.local/share/eaccode/approvals.json`` (or
``%LOCALAPPDATA%/eaccode/approvals.json`` on Windows).

Session-scoped rules live only in-memory and are lost when the
agent exits. Once-scoped rules are persisted but consumed once
and then removed.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from eaccode.workspace import PathRule


@dataclass
class ApprovalsStore:
    """Persistent rule store for always-scoped workspace exceptions."""

    path: Path

    def load(self) -> list[PathRule]:
        """Load always-scoped rules from disk.

        Returns an empty list when the file doesn't exist or is
        corrupted. Once- and session-scoped rules are NOT persisted.
        """
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        rules: list[PathRule] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            try:
                rules.append(PathRule(
                    raw=str(entry.get("raw", "")),
                    scope=str(entry.get("scope", "always")),
                    kind=str(entry.get("kind", "allow")),
                ))
            except ValueError:
                continue
        return rules

    def save(self, rules: list[PathRule]) -> None:
        """Persist always-scoped rules atomically.

        Session- and once-scoped rules are skipped (they live only
        in memory).
        """
        persistent = [
            asdict(r)
            for r in rules
            if r.scope == "always"
        ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write - tmp + rename so a crash mid-write can't
        # leave a half-written approvals.json.
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent),
            prefix=".approvals.",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(persistent, fh, indent=2)
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def clear(self) -> None:
        """Remove the persistence file."""
        if self.path.exists():
            self.path.unlink()


def default_store_path() -> Path:
    """Return the default ``approvals.json`` path (cross-platform)."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "eaccode" / "approvals.json"
    return Path.home() / ".local" / "share" / "eaccode" / "approvals.json"


__all__ = ["ApprovalsStore", "default_store_path"]