"""Agent core: ReAct-style loop with tool calling (Phase A4).

The agent alternates between model turns (which may request tool calls) and
tool execution turns, until the model answers without tool calls or the turn
budget is exhausted. Synchronous and testable — the REPL/TUI drive it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from eaccode import config as cfg
from eaccode import router, skills

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


class Agent:
    """A minimal ReAct agent: model <-> tools until a final answer."""

    def __init__(
        self,
        conf: dict[str, Any] | None = None,
        tools: list[Tool] | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        use_skills: bool = True,
    ) -> None:
        self.conf = conf or cfg.load_config()
        self.system_prompt = system_prompt
        self.tools = {tool.name: tool for tool in (tools or [])}
        self.use_skills = use_skills

    def _complete(
        self, messages: list[dict[str, Any]], max_output_tokens: int
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
        response = router.completion_response(
            chain[0], messages, self.conf, timeout=90.0, extra_kwargs=kwargs
        )
        return parse_response(response)

    def _execute_tool(self, call: ToolCall) -> str:
        tool = self.tools.get(call.name)
        if tool is None:
            return f"Error: unknown tool: {call.name}"
        try:
            result = tool.func(**call.arguments)
        except Exception as exc:  # tool bugs must not kill the loop
            return f"Error: tool {call.name} failed: {exc}"
        return str(result)

    def run(
        self,
        messages: list[dict[str, str]],
        max_turns: int = MAX_TURNS,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> list[dict[str, Any]]:
        """Run the loop; returns the full conversation including tool results."""
        system_content = self.system_prompt
        if self.use_skills:
            last_user = next(
                (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
            )
            system_content = f"{system_content}{skills.injection_block(last_user)}"
        history: list[dict[str, Any]] = [
            {"role": "system", "content": system_content}
        ]
        history.extend(messages)

        for _ in range(max_turns):
            content, calls = self._complete(history, max_output_tokens)
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
            for call in calls:
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": self._execute_tool(call),
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
