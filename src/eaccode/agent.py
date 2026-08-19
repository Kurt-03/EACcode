"""Agent core: ReAct-style loop with tool calling.

The agent alternates between model turns (which may request tool calls) and
tool execution turns, until the model answers without tool calls or the turn
budget is exhausted. Synchronous and testable — the REPL/TUI drive it.

Streaming is delegated to the provider registry (`eaccode.providers`). Each
provider adapter normalizes its wire format into `StreamChunk` so the agent
loop never sees Anthropic-specific events.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from eaccode import config as cfg
from eaccode import models_dev, permissions, skills
from eaccode.providers import base as provider_base
from eaccode.providers import registry as provider_registry

DEFAULT_SYSTEM_PROMPT = (
    "You are eaccode, a self-improving generalist agent running locally "
    "with the user's own API keys. Be concise, precise and honest. "
    "Use tools when they help, never invent tool results.\n\n"
    "## Tool usage (REQUIRED)\n"
    "Only call tools that appear in the tool manifest we sent you. "
    "Never invent tool names. If you find yourself wanting to run "
    "`echo`, `del`, `dir`, `pwd`, `ls`, `cat`, `find`, `mkdir`, `rm`, "
    "`cp`, `mv` or any other shell builtin - these are NOT eaccode tools. "
    "Instead use the dedicated eaccode tools:\n"
    "  - To list directory contents: use `list_files` (NOT `ls` or `dir`)\n"
    "  - To read a file's content: use `read_file` (NOT `cat` or `type`)\n"
    "  - To write/overwrite a file: use `write_file` (NOT `echo >` or `Set-Content`)\n"
    "  - To modify an existing file: use `patch_file` (single replace) "
    "or `file_edit` (line-based) or `patch_multiple` (atomic batch). "
    "NOT `sed` or in-file `echo >`\n"
    "  - To search inside files: use `search_files` or `repo_search` "
    "(NOT `grep`, `rg`, or `find /...`)\n"
    "  - To search across the repo: use `repo_scan` (NOT `find .`)\n"
    "  - To run a build / tests / install / git / npm / cargo / etc.: "
"use `run_command` - this is the ONE tool that runs shell commands. "
"Pick `run_command` for things like `pytest`, `git status`, `npm "
"install`, `cargo build`, `make`, `python x.py`.\n"
"  - For interactive shells (cd, pwd, ls, del via cmd.exe): use "
"`run_command` with the full command line.\n"
"  - For long-running commands (server, watch, daemon): use "
"`run_command` with a generous timeout (max 600s).\n"
    "`create_skill` / `improve_skill` (NOT vi/creating files in /skills/)\n"
    "  - To store/recall facts: use `memory_add`/`memory_remove` "
    "(NOT writing to MEMORY.md directly)\n\n"
    "## Workflow patterns\n"
    "- For 'show me X file': call `read_file(path=\"<full-or-relative-path>\")`\n"
    "- For 'list dir contents' or 'what is on my desktop': call "
    "`list_files(path=\"<path>\")`\n"
    "- For 'delete these files': execute 'rm <files>' or 'del <files>' in your "
    "own terminal, then confirm to eaccode.\n"
    "- For 'edit line 12 of file X': use `file_edit` or "
    "`patch_file` - both are undoable via `undo_edit`\n"
    "- For 'apply these N edits': prefer `patch_multiple` (atomic, "
    "all-or-nothing) over N separate `patch_file` calls\n\n"
    "Never use `echo <text> > <path>` for file creation. "
    "`write_file` is the dedicated tool and works on Windows + Unix "
    "consistently, includes undo, and respects the permission gate."
)

MAX_TURNS = 8
MAX_OUTPUT_TOKENS = 1024


# Re-export for back-compat with tests/internal callers
from eaccode.providers.base import ToolCall  # noqa: E402,F401


class AgentError(Exception):
    """Raised for agent-level failures (no model, loop crash)."""


@dataclass
class Tool:
    """A callable tool exposed to the model.

    Tags (planned 08-18 hardens by audit):
      - mutates: True if the tool changes persistent state.
        READ_ONLY_TOOLS detection uses this tag directly.
      - always_ask: True if every call must prompt (even after the user
        has approved the same tool earlier in this session).
      - returns: short human-readable description of the success output
        and the Error-prefix failure string. Anthropic SDK reads the
        Tool description only, so the returns docstring has to live there
        OR be passed via description suffix.
    """

    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    mutates: bool = False
    always_ask: bool = False
    returns: str = ""


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


def _state_to_provider(
    conf: dict[str, Any], model_id: str = ""
) -> tuple[provider_base.Provider, provider_base.Provider, str]:
    """Resolve the configured provider/model to a Provider instance.

    Returns (provider, tools_view, model_id). The provider is fetched via
    the registry, which caches per (provider_name, base_url, api_key).

    Raises AgentError when no model is configured or the provider cannot
    be resolved.
    """
    chain = _model_chain(conf)
    if not chain:
        raise AgentError(
            "no default model configured - run 'model set-default <model>'"
        )
    chosen = model_id or chain[0]
    provider_name, _, model_short = chosen.partition("/")
    provider_config = (conf.get("providers") or {}).get(provider_name, {})
    provider = provider_registry.get(
        provider_name, provider_config, model=chosen
    )
    return provider, provider, chosen


def _model_chain(conf: dict[str, Any]) -> list[str]:
    """Default model followed by the fallback chain."""
    model = conf.get("model") or {}
    chain: list[str] = []
    if model.get("default"):
        chain.append(model["default"])
    chain.extend(model.get("fallback") or [])
    return chain


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

    def _max_tokens_for(self, model_id: str) -> int:
        """Pick max_tokens from models.dev, fall back to MAX_OUTPUT_TOKENS."""
        provider_name, _, model_short = model_id.partition("/")
        try:
            md = models_dev.get_max_output_tokens(provider_name, model_short)
        except Exception:
            md = 0
        return md or MAX_OUTPUT_TOKENS

    def _complete(
        self,
        messages: list[dict[str, Any]],
        max_output_tokens: int,
        on_token: Any = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[str | None, list[ToolCall]]:
        """One model turn: stream or one-shot, return (content, tool_calls).

        ``tools``: override the tool list sent to the model. Pass an empty
        list (or never any) for tool-free final-answer attempts. If None
        (default), uses the agent's registered tools.
        """
        _, _, model_id = _state_to_provider(self.conf)
        provider_name, _, model_short = model_id.partition("/")
        provider_config = (self.conf.get("providers") or {}).get(provider_name, {})
        provider = provider_registry.get(
            provider_name, provider_config, model=model_id
        )

        if tools is None:
            tool_schemas = (
                [_tool_schema(tool) for tool in self.tools.values()]
                if self.tools
                else None
            )
        else:
            tool_schemas = tools or None
        max_tokens = max_output_tokens or self._max_tokens_for(model_id)

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: dict[int, ToolCall] = {}

        for chunk in provider.stream(
            messages,
            max_tokens=max_tokens,
            tools=tool_schemas,
        ):
            if chunk.kind == "text" and chunk.content:
                content_parts.append(chunk.content)
                if on_token is not None:
                    _safe_on_token(on_token, chunk)
            elif chunk.kind == "reasoning" and chunk.content:
                reasoning_parts.append(chunk.content)
                if on_token is not None:
                    _safe_on_token(on_token, chunk)
            elif chunk.kind == "tool_call" and chunk.tool_call is not None:
                # The provider adapter should deliver at most one tool_call
                # per tool_use block; we use the id as the dedup key.
                tool_calls[chunk.tool_call.id or id(chunk.tool_call)] = chunk.tool_call
            elif chunk.kind == "done":
                break

        content = "".join(content_parts) or None
        if reasoning_parts and not content:
            # No answer content but the model only produced reasoning. Surface
            # the reasoning as the answer so the user still sees something.
            content = "".join(reasoning_parts)
        return content, list(tool_calls.values())

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
        on_chunk: Any = None,
    ) -> list[dict[str, Any]]:
        """Run the loop; returns the full conversation including tool results.

        ``cancel_event``: a threading.Event that is checked between turns —
        when set, the loop stops cleanly with a cancellation message (used
        by the subagent timeout guard).

        ``on_token``: legacy callback interface: accepts a single string
        (text delta) or a (text, kind) tuple. Deprecated — prefer
        ``on_chunk`` which receives StreamChunk objects.

        ``on_chunk``: optional callback receiving StreamChunk objects as
        they stream from the provider. The agent does not depend on either
        callback being present.
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

        # Try one final completion WITHOUT tools so the model has a chance
        # to summarize what it found. If the model still emits tool_calls,
        # drop them and treat as failure. If the provider raises
        # StopIteration (test fake) we just stop cleanly.
        history.append(
            {
                "role": "user",
                "content": (
                    f"You have used {max_turns} turns without giving a final answer. "
                    "Synthesize what you have so far into a concise answer to my "
                    "original question. Do not call any more tools."
                ),
            }
        )
        try:
            content, calls = self._complete(
                history, max_output_tokens, on_token=on_token, tools=[]
            )
        except (StopIteration, TypeError):
            # StopIteration happens with FakeProvider that has fixed response
            # count. TypeError if _complete lacks tools= override.
            content, _ = self._complete(history, max_output_tokens, on_token=on_token)
        history.append({"role": "assistant", "content": content or ""})
        return history

    def last_text(self, history: list[dict[str, Any]]) -> str:
        """Return the final assistant text from a run's history."""
        for message in reversed(history):
            if message["role"] == "assistant" and message.get("content"):
                return message["content"]
        return ""


def _safe_on_token(on_token: Any, chunk: StreamChunk) -> None:
    """Forward a StreamChunk to the legacy on_token callback.

    Supports:
      - on_token(str)              (legacy single-arg)
      - on_token(str, kind=...)      (palette's reasoning-style)
      - on_token(StreamChunk)        (newest, full-delivery)
    """
    try:
        on_token(chunk.content, kind=chunk.kind)
    except TypeError:
        try:
            on_token(chunk.content)
        except TypeError:
            on_token(chunk)
