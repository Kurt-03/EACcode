"""Subagents (Phase B5): isolated agents with restricted tools.

The main agent spawns focused workers via ``spawn_subagent``. Each worker
gets its own Agent instance (no skills, no nudges, max 6 turns), only the
requested tools and an explicit context. At most ``MAX_PARALLEL`` run at
once; the rest wait on a semaphore.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from eaccode import config as cfg
from eaccode.agent import Agent, Tool

MAX_PARALLEL = 6
SUBAGENT_TIMEOUT = 180
SUBAGENT_MAX_TURNS = 6

SUBAGENT_SYSTEM_PROMPT = (
    "You are a focused subagent. Answer the task using ONLY the provided tools "
    "and context. Be precise and concise. Do not ask questions, do not invent "
    "tool results."
)


class SubagentError(Exception):
    """Raised for subagent-level failures."""


class SubagentPool:
    """Runs subagents with a concurrency limit and a per-run timeout."""

    def __init__(
        self,
        conf: dict[str, Any] | None = None,
        max_parallel: int = MAX_PARALLEL,
        agent_factory: Callable[[], Agent] | None = None,
    ) -> None:
        self._conf = conf
        self._agent_factory = agent_factory
        self._semaphore = threading.BoundedSemaphore(max_parallel)
        self.active = 0
        self._lock = threading.Lock()

    def run(
        self,
        task: str,
        tool_map: list[Tool],
        context: str = "",
        timeout: float = SUBAGENT_TIMEOUT,
    ) -> str:
        """Run one subagent; returns its final answer or an error string."""
        with self._semaphore:
            with self._lock:
                self.active += 1
            try:
                return self._run_limited(task, tool_map, context, timeout)
            finally:
                with self._lock:
                    self.active -= 1

    def _run_limited(
        self,
        task: str,
        tool_map: list[Tool],
        context: str,
        timeout: float,
    ) -> str:
        agent = (
            self._agent_factory()
            if self._agent_factory
            else Agent(
                conf=self._conf or cfg.load_config(),
                tools=tool_map,
                system_prompt=SUBAGENT_SYSTEM_PROMPT,
                use_skills=False,
                memory_nudge_interval=0,
            )
        )
        messages: list[dict[str, str]] = []
        if context:
            messages.append({"role": "system", "content": f"## Context\n{context}"})
        messages.append({"role": "user", "content": task})

        result: dict[str, Any] = {}

        def work() -> None:
            try:
                history = agent.run(messages, max_turns=SUBAGENT_MAX_TURNS)
                result["answer"] = agent.last_text(history)
            except Exception as exc:
                result["error"] = str(exc)

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            return f"Error: subagent timed out after {timeout:.0f}s"
        if "error" in result:
            return f"Error: subagent failed: {result['error']}"
        return result.get("answer") or "(no answer)"


def make_subagent_tool(
    pool: SubagentPool,
    tool_registry: dict[str, Tool],
    conf: dict[str, Any],
) -> Tool:
    """Build the ``spawn_subagent`` agent tool bound to a pool."""

    def spawn(
        task: str,
        tools: list[str] | None = None,
        context: str = "",
    ) -> str:
        names = tools or []
        selected: list[Tool] = []
        for name in names:
            tool = tool_registry.get(name)
            if tool is None:
                available = ", ".join(sorted(tool_registry))
                return f"Error: unknown tool: {name} (available: {available})"
            selected.append(tool)
        if not selected:
            return "Error: specify at least one tool for the subagent"
        return pool.run(task, selected, context)

    return Tool(
        "spawn_subagent",
        "Spawn a focused subagent with an isolated context. Give it a clear "
        "task, the list of tools it may use, and any context it needs. "
        "Returns the subagent's final answer.",
        spawn,
        {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}},
                "context": {"type": "string"},
            },
            "required": ["task", "tools"],
        },
    )
