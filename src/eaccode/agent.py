"""Agent core: ReAct-style loop with tool calling (Phase A4).

The agent alternates between model turns (which may request tool calls) and
tool execution turns, until the model answers without tool calls or the turn
budget is exhausted. Synchronous and testable — the REPL/TUI drive it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from eaccode import config as cfg
from eaccode import permissions, router, skills

DEFAULT_SYSTEM_PROMPT = (
    "You are eaccode, a self-improving generalist agent running locally "
    "with the user's own API keys. Be concise, precise and honest. "
    "Use tools when they help, never invent tool results."
)

MAX_TURNS = 8
MAX_OUTPUT_TOKENS = 1024


class AgentError(Exception):
    """Raised for agent-level failures (no model, loop crash)."""


@dataclass
class Tool:
    """A callable tool exposed to the model."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """One tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


def _tool_schema(tool: Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters
            or {"type": "object", "properties": {}},
        },
    }


def parse_response(response: Any) -> tuple[str | None, list[ToolCall]]:
    """Extract (content, tool_calls) from a LiteLLM completion response."""
    message = response.choices[0].message
    content = message.content
    calls: list[ToolCall] = []
    for index, raw in enumerate(message.tool_calls or []):
        try:
            arguments = json.loads(raw.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        calls.append(
            ToolCall(
                id=raw.id or f"call_{index}",
                name=raw.function.name,
                arguments=arguments,
            )
        )
    return content, calls


def tool_guide(tools: dict[str, Tool]) -> str:
    """Human-readable tool manifest for the system prompt.

    Lists every tool with its description plus usage guidance so the
    model knows what exists and when to reach for it.
    """
    lines = [
        "\n\n## Available tools",
        "You have tools - use them instead of guessing. Tool calls run "
        "through the permission gate (see mode above).",
    ]
    for name in sorted(tools):
        tool = tools[name]
        lines.append(f"- `{name}`: {tool.description}")
    lines.append(
        "\nTypical coding flow: repo_scan to understand the project, "
        "read_file for details, patch_file/file_edit for changes, "
        "run_tests to verify, git_status/git_diff to inspect, git_commit "
        "only after tests pass. Memory tools store durable facts."
    )
    return "\n".join(lines)


class Agent:
    """A minimal ReAct agent: model <-> tools until a final answer."""

    def __init__(
        self,
        conf: dict[str, Any] | None = None,
        tools: list[Tool] | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        use_skills: bool = True,
        memory_nudge_interval: int = 10,
        permission_manager: permissions.PermissionManager | None = None,
    ) -> None:
        self.conf = conf or cfg.load_config()
        self.system_prompt = system_prompt
        self.tools = {tool.name: tool for tool in (tools or [])}
        if self.tools and self.system_prompt:
            self.system_prompt = f"{self.system_prompt}\n\n{tool_guide(self.tools)}"
        self.use_skills = use_skills
        self.memory_nudge_interval = memory_nudge_interval
        self.permission_manager = permission_manager
        self._memory_runs = 0

    def _complete(
        self,
        messages: list[dict[str, Any]],
        max_output_tokens: int,
        on_token: Any = None,
    ) -> tuple[str | None, list[ToolCall]]:
        chain = router.model_chain(self.conf)
        if not chain:
            raise router.ModelError(
                "no default model configured - run 'model set-default <model>'"
            )
        kwargs: dict[str, Any] = {"max_tokens": max_output_tokens}
        if self.tools:
            kwargs["tools"] = [_tool_schema(tool) for tool in self.tools.values()]
            kwargs["tool_choice"] = "auto"
        if on_token is None:
            response = router.completion_response(
                chain[0], messages, self.conf, timeout=90.0, extra_kwargs=kwargs
            )
            return parse_response(response)
        # ---- streaming path: emit text deltas, assemble tool calls ----
        content_parts: list[str] = []
        fragments: dict[int, dict[str, str]] = {}
        response = router.stream_completion(
            chain[0], messages, self.conf, timeout=90.0, extra_kwargs=kwargs
        )
        for chunk in response:
            if not getattr(chunk, "choices", None):
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                content_parts.append(text)
                on_token(text)
            for tc in getattr(delta, "tool_calls", None) or []:
                index = getattr(tc, "index", 0)
                frag = fragments.setdefault(index, {"id": "", "name": "", "args": ""})
                if getattr(tc, "id", None):
                    frag["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        frag["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        frag["args"] += fn.arguments
        content = "".join(content_parts) or None
        if fragments:
            calls = []
            for index in sorted(fragments):
                frag = fragments[index]
                try:
                    args = json.loads(frag["args"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                calls.append(
                    ToolCall(
                        id=frag["id"] or f"call_{index}",
                        name=frag["name"],
                        arguments=args,
                    )
                )
            return content, calls
        return content, []

    def _execute_tool(self, call: ToolCall) -> str:
        tool = self.tools.get(call.name)
        if tool is None:
            return f"Error: unknown tool: {call.name}"
        if call.name.startswith("memory_"):
            self._memory_runs = 0  # agent curated memory -> nudge timer resets
        # Permission gate (C1): every tool is checked before it runs.
        if self.permission_manager is not None:
            decision = self.permission_manager.check(call.name, call.arguments)
            if not decision.allow:
                return f"Error: permission denied ({decision.reason})"
        try:
            if call.name == "run_command":
                # run_command has its own interactive gate; the loop already
                # decided, so tell it to skip the second prompt.
                from eaccode import tools as tools_mod  # lazy: avoids import cycle

                tools_mod._loop_permission_checked = True
                try:
                    result = tool.func(**call.arguments)
                finally:
                    tools_mod._loop_permission_checked = False
            else:
                result = tool.func(**call.arguments)
        except Exception as exc:  # tool bugs must not kill the loop
            return f"Error: tool {call.name} failed: {exc}"
        return str(result)

    def run(
        self,
        messages: list[dict[str, str]],
        max_turns: int = MAX_TURNS,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
        cancel_event: Any | None = None,
        on_token: Any = None,
    ) -> list[dict[str, Any]]:
        """Run the loop; returns the full conversation including tool results.

        ``cancel_event``: a threading.Event that is checked between turns —
        when set, the loop stops cleanly with a cancellation message (used
        by the subagent timeout guard).

        ``on_token``: optional callback receiving text deltas while the
        model streams. It also receives "" at the start of every round so
        the UI can open a fresh line per round.
        """
        self._memory_runs += 1
        system_content = self.system_prompt
        if self.use_skills:
            last_user = next(
                (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
            )
            system_content = f"{system_content}{skills.injection_block(last_user)}"
        if self.memory_nudge_interval and self._memory_runs % self.memory_nudge_interval == 0:
            system_content += (
                "\n\n## Memory nudge\n"
                "Review your persistent memory (memory_add/replace/remove/apply_batch): "
                "merge overlapping facts, remove stale ones, store anything important "
                "you learned recently. Keep it compact."
            )
        history: list[dict[str, Any]] = [
            {"role": "system", "content": system_content}
        ]
        history.extend(messages)

        for _ in range(max_turns):
            if cancel_event is not None and cancel_event.is_set():
                history.append(
                    {"role": "assistant", "content": "(cancelled by timeout guard)"}
                )
                return history
            if on_token is not None:
                on_token("")  # round marker: UI opens a fresh log line
            content, calls = self._complete(
                history, max_output_tokens, on_token=on_token
            )
            if not calls:
                history.append({"role": "assistant", "content": content or ""})
                return history

            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for call in calls
                ],
            }
            history.append(assistant_message)
            # Parallel tool execution: independent calls of one turn run
            # concurrently (subagents and long-running tools benefit).
            # Capped so a turn with many calls cannot spawn unbounded threads.
            if len(calls) > 1:
                workers = min(len(calls), 6)
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    results = list(pool.map(self._execute_tool, calls))
            else:
                results = [self._execute_tool(calls[0])]
            for call, content in zip(calls, results, strict=True):
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": content,
                    }
                )

        history.append(
            {
                "role": "assistant",
                "content": f"(stopped: max turns ({max_turns}) reached)",
            }
        )
        return history

    def last_text(self, history: list[dict[str, Any]]) -> str:
        """Return the final assistant text from a run's history."""
        for message in reversed(history):
            if message["role"] == "assistant" and message.get("content"):
                return message["content"]
        return ""
