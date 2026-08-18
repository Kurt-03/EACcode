"""Hermes-style denial breaker (Phase G.11, Plan G v4, H5/H6).

When the aux-LLM returns DENY for several consecutive calls in the
same session, the next call is blocked outright (a circuit breaker).

Mirrors approval.py:_record_denial / _reset_denials /
_denial_breaker_addendum from Hermes.
"""

from __future__ import annotations

import threading
from typing import Optional


class DenialBreaker:
    """Tracks consecutive guardian-denial verdicts per session."""

    def __init__(self, threshold: int = 3, max_sessions: int = 256) -> None:
        self._threshold = threshold
        self._max_sessions = max_sessions
        self._tally: dict[str, int] = {}
        self._lock = threading.Lock()

    def set_threshold(self, threshold: int) -> None:
        self._threshold = max(0, threshold)

    @property
    def threshold(self) -> int:
        return self._threshold

    def record(self, session_key: str) -> int:
        """Increment the tally for ``session_key`` and return new count."""
        with self._lock:
            count = self._tally.pop(session_key, 0) + 1
            self._tally[session_key] = count
            # LRU eviction - drop oldest when we exceed the cap.
            while len(self._tally) > self._max_sessions:
                self._tally.pop(next(iter(self._tally)))
            return count

    def reset(self, session_key: str) -> None:
        """Clear the tally for ``session_key`` (called on approve)."""
        with self._lock:
            self._tally.pop(session_key, None)

    def count(self, session_key: str) -> int:
        with self._lock:
            return self._tally.get(session_key, 0)

    def addendum(self, session_key: str) -> str:
        """Return the hard-stop text when the breaker has tripped.

        Empty string below the threshold (or when disabled), otherwise
        a leading-space addendum the caller appends verbatim to the
        deny message returned to the model.
        """
        with self._lock:
            count = self._tally.get(session_key, 0)
        if self._threshold <= 0 or count < self._threshold:
            return ""
        return (
            f" Denial-breaker tripped: {count} consecutive guardian-denial"
            " verdicts for this session; refusing further commands. Use"
            " the `/approvals reset` slash command (or restart the REPL)"
            " to clear."
        )


# Module-level singleton used by the permission manager. Tests can
# patch this via monkeypatch.
DEFAULT_DENIAL_BREAKER = DenialBreaker()


def get_denial_breaker() -> DenialBreaker:
    return DEFAULT_DENIAL_BREAKER


__all__ = [
    "DenialBreaker",
    "DEFAULT_DENIAL_BREAKER",
    "get_denial_breaker",
]
