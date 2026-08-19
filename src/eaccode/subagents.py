"""Subagents (Phase B5): isolated agents with restricted tools.

The main agent spawns focused workers via ``spawn_subagent``. Each worker
gets its own Agent instance (no skills, no nudges, max 6 turns), only the
requested tools and an explicit context. At most ``MAX_PARALLEL`` run at
once; the rest wait on a semaphore.
"""

from __future__ import annotations

import threading
import time
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




def _make_subagent_chunk_forwarder(
    task: str,
    session_key: str,
    parent_on_chunk,
):
    """Return an on_chunk callback that wraps inner chunks with sub-agent info.

    If parent_on_chunk is None (subagent invoked by model directly),
    return None and the sub-agent's chunks are silently dropped.
    """
    if parent_on_chunk is None:
        return None
    from eaccode.providers.base import StreamChunk
    from dataclasses import replace

    def forward(chunk: StreamChunk) -> None:
        if chunk.kind in {"text", "reasoning", "error", "done"}:
            parent_on_chunk(chunk)
            return
        if chunk.kind in {"tool_start", "tool_end", "tool_error"}:
            new_name = (
                f"  \u21b3 {chunk.tool_name}" if chunk.tool_name else chunk.tool_name
            )
            parent_on_chunk(replace(chunk, tool_name=new_name))
            return
        parent_on_chunk(chunk)
    return forward


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
        parent_session_key: str | None = None,
    ) -> str:
        """Run one subagent; returns its final answer or an error string.

        The subagent gets its own session_key (``sub-{ts}``) so it has
        independent workspace / permission / todo state from its parent
        (Plan J thread-safety).
        """
        sub_session_key = f"sub-{int(time.time())}-{id(self)}"
        sub_on_chunk = getattr(self, "_parent_on_chunk", None)
        with self._semaphore:
            with self._lock:
                self.active += 1
            try:
                return self._run_limited(task, tool_map, context, timeout, sub_session_key)
            finally:
                with self._lock:
                    self.active -= 1

    def _run_limited(
        self,
        task: str,
        tool_map: list[Tool],
        context: str,
        timeout: float,
        session_key: str,
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
                permission_manager=None,  # agent constructs its own
            )
        )
        messages: list[dict[str, str]] = []
        if context:
            messages.append({"role": "system", "content": f"## Context\n{context}"})
        messages.append({"role": "user", "content": task})

        cancel_event = threading.Event()
        result: dict[str, Any] = {}

        # Plan K K.5: forward parent's on_chunk so sub-agent tool calls
        # are visible in the TUI/CLI with sub_agent_id marker.
        parent_on_chunk = getattr(self, "_parent_on_chunk", None)

        def work() -> None:
            try:
                history = agent.run(
                    messages,
                    max_turns=SUBAGENT_MAX_TURNS,
                    cancel_event=cancel_event,
                    session_key=session_key,
                    on_chunk=_make_subagent_chunk_forwarder(
                        task, session_key, parent_on_chunk,
                    ),
                )
                result["answer"] = agent.last_text(history)
            except Exception as exc:
                result["error"] = str(exc)

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            # Signal the loop to stop at the next turn boundary; the daemon
            # thread then exits on its own (no uncontrolled tool actions).
            cancel_event.set()
            return f"Error: subagent timed out after {timeout:.0f}s (cancelled)"
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
        # tools may be empty: a reasoning-only subagent is valid
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
