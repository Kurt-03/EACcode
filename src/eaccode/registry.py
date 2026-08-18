"""Tool registry (Phase G.1, Plan G v5).

Hermes has a singleton ``ToolRegistry`` that every tool file calls
``registry.register(...)`` against at module-import time. We implement
the same pattern for eaccode so future plugins can override built-in
tools with explicit operator opt-in.

Mirrors tools/registry.py from Hermes.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class ToolEntry:
    """One registered tool."""

    name: str
    toolset: str
    schema: dict[str, Any]
    handler: Callable[..., Any]
    check_fn: Callable[[], bool] | None = None
    requires_env: list[str] = field(default_factory=list)
    is_async: bool = False
    description: str = ""
    emoji: str = ""
    max_result_size_chars: int | None = None
    dynamic_schema_overrides: Callable[[], dict[str, Any]] | None = None
    override: bool = False


class ToolRegistry:
    """Singleton registry. Thread-safe."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}
        self._toolset_checks: dict[str, Callable[[], bool]] = {}
        self._toolset_aliases: dict[str, str] = {}
        self._lock = threading.RLock()
        self._generation = 0

    # ---- snapshot helpers ----

    def _snapshot(self) -> tuple[list[ToolEntry], dict[str, Callable[[], bool]]]:
        with self._lock:
            return list(self._tools.values()), dict(self._toolset_checks)

    # ---- register / deregister ----

    def register(self, entry: ToolEntry) -> None:
        """Register a tool. Honours ``override=True`` if needed."""
        with self._lock:
            existing = self._tools.get(entry.name)
            if existing is not None and existing.toolset != entry.toolset:
                if not entry.override:
                    logger.warning(
                        "Tool %s already in toolset %s; "
                        "override=True required to replace",
                        entry.name, existing.toolset,
                    )
                    return
            self._tools[entry.name] = entry
            self._generation += 1

    def deregister(self, name: str) -> None:
        with self._lock:
            entry = self._tools.pop(name, None)
            if entry is None:
                return
            self._generation += 1

    # ---- lookups ----

    def get_entry(self, name: str) -> ToolEntry | None:
        with self._lock:
            return self._tools.get(name)

    def get_tool_names_for_toolset(self, toolset: str) -> list[str]:
        with self._lock:
            return sorted(
                entry.name for entry in self._tools.values()
                if entry.toolset == toolset
            )

    def get_registered_toolset_names(self) -> list[str]:
        with self._lock:
            return sorted({entry.toolset for entry in self._tools.values()})

    # ---- definitions ----

    def get_definitions(
        self, tool_names: set[str], *, quiet: bool = False,
    ) -> list[dict[str, Any]]:
        """Return OpenAI-format tool definitions for the requested tools."""
        result: list[dict[str, Any]] = []
        with self._lock:
            for name in sorted(tool_names):
                entry = self._tools.get(name)
                if entry is None:
                    continue
                if entry.check_fn is not None:
                    try:
                        ok = entry.check_fn()
                    except Exception as exc:
                        logger.debug("check_fn for %s raised: %s", name, exc)
                        ok = False
                    if not ok:
                        if not quiet:
                            logger.debug("Tool %s unavailable", name)
                        continue
                schema = {"type": "function", "function": dict(entry.schema)}
                schema["function"]["name"] = entry.name
                if entry.description:
                    schema["function"]["description"] = entry.description
                if entry.dynamic_schema_overrides is not None:
                    try:
                        overrides = entry.dynamic_schema_overrides()
                        if isinstance(overrides, dict):
                            schema["function"].update(overrides)
                    except Exception as exc:
                        logger.warning(
                            "dynamic_schema_overrides for %s raised %s", name, exc
                        )
                if entry.max_result_size_chars is not None:
                    schema.setdefault("function", {}).setdefault(
                        "metadata", {}
                    )["max_result_size_chars"] = entry.max_result_size_chars
                result.append(schema)
        return result

    # ---- generation counter (for cache invalidation) ----

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation


REGISTRY = ToolRegistry()


def register(entry: ToolEntry) -> None:
    REGISTRY.register(entry)


def deregister(name: str) -> None:
    REGISTRY.deregister(name)


def get_entry(name: str) -> ToolEntry | None:
    return REGISTRY.get_entry(name)


def get_definitions(tool_names: set[str], *, quiet: bool = False) -> list[dict[str, Any]]:
    return REGISTRY.get_definitions(tool_names, quiet=quiet)


__all__ = [
    "ToolEntry",
    "ToolRegistry",
    "REGISTRY",
    "register",
    "deregister",
    "get_entry",
    "get_definitions",
]
