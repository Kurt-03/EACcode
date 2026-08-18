"""Tool-call middlewares (Phase G.10, Plan G v5).

Hermes has a middleware system that fires pre-request and
pre-execution. Plugins register callables in two phases:

  - PRE_REQUEST:    receives (name, args) and may rewrite args or veto
  - PRE_EXECUTION:  receives (name, args) and may short-circuit by
                    returning a string result

Mirrors tools/model_tools.py:_tool_request_middleware /
tools/model_tools.py:_tool_execution_middleware.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


PRE_REQUEST = "pre_request"
PRE_EXECUTION = "pre_execution"


# Each middleware returns either None (continue) or a value:
# - For PRE_REQUEST, returning a dict replaces the args.
# - For PRE_EXECUTION, returning a string short-circuits the tool.
Middleware = Callable[[str, dict[str, Any]], dict[str, Any] | str | None]


@dataclass
class _Registry:
    pre_request: list[Middleware] = None  # type: ignore[assignment]
    pre_execution: list[Middleware] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.pre_request is None:
            self.pre_request = []
        if self.pre_execution is None:
            self.pre_execution = []


_REGISTRY = _Registry()


def register_pre_request(fn: Middleware) -> None:
    _REGISTRY.pre_request.append(fn)


def register_pre_execution(fn: Middleware) -> None:
    _REGISTRY.pre_execution.append(fn)


def unregister(fn: Middleware) -> None:
    if fn in _REGISTRY.pre_request:
        _REGISTRY.pre_request.remove(fn)
    if fn in _REGISTRY.pre_execution:
        _REGISTRY.pre_execution.remove(fn)


def clear() -> None:
    """Drop every registered middleware (for tests / config hot-reload)."""
    _REGISTRY.pre_request.clear()
    _REGISTRY.pre_execution.clear()


def run_pre_request(name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """Run every pre-request middleware in order. Return first non-None
    rewritten args, or None to abort.
    """
    for fn in list(_REGISTRY.pre_request):
        try:
            out = fn(name, args)
        except Exception as exc:
            logger.warning("pre_request middleware raised: %s", exc)
            continue
        if isinstance(out, dict):
            return out
    return None


def run_pre_execution(name: str, args: dict[str, Any]) -> str | None:
    """Run every pre-execution middleware. Return first non-None short-circuit."""
    for fn in list(_REGISTRY.pre_execution):
        try:
            out = fn(name, args)
        except Exception as exc:
            logger.warning("pre_execution middleware raised: %s", exc)
            continue
        if isinstance(out, str):
            return out
    return None
