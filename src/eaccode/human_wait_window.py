"""human_wait_window ContextVar (Phase C.3, Plan C).

Pauses the batch-deadline timer while a user is being asked for input.
Hermes idea: if you're waiting on the user, you can't be timed out by
the concurrent batch deadline.

Usage:

    from eaccode.human_wait_window import human_wait_window
    with human_wait_window():
        result = prompt_user(...)
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar
from typing import Iterator


# ContextVar tracks whether a permission/ask prompt is in progress.
# Downstream code (e.g. cron, batch deadline watchdog) can poll
# `is_human_wait_active()` and pause their countdown while True.
_human_wait_depth: ContextVar[int] = ContextVar("eaccode_human_wait_depth", default=0)


def is_human_wait_active() -> bool:
    """True when at least one human_wait_window is open on this task."""
    return _human_wait_depth.get() > 0


@contextlib.contextmanager
def human_wait_window() -> Iterator[None]:
    """Mark the current task as waiting on the user.

    Nested windows work (counter-style): only return to the previous
    value when the outermost window exits.
    """
    token = _human_wait_depth.set(_human_wait_depth.get() + 1)
    try:
        yield
    finally:
        _human_wait_depth.reset(token)
