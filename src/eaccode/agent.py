"""Agent core: ReAct-style loop with tool calling.

The agent alternates between model turns (which may request tool calls) and
tool execution turns, until the model answers without tool calls or the turn
budget is exhausted. Synchronous and testable — the REPL/TUI drive it.

Streaming is delegated to the provider registry (`eaccode.providers`). Each
provider adapter normalizes its wire format into `StreamChunk` so the agent
loop never sees Anthropic-specific events.
"""

from __future__ import annotations

import time

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from eaccode import config as cfg
from eaccode import models_dev, permissions, skills
from eaccode.providers import base as provider_base
from eaccode.providers import registry as provider_registry
from eaccode import compaction as compactor
from eaccode import token_counter

DEFAULT_SYSTEM_PROMPT = (
    "You are eaccode, a self-improving coding agent running locally. "
    "Be concise, precise, action-oriented.\n\n"
    "## Style (always follow)\n"
    "- Max 3-5 sentences unless showing code or a list.\n"
    "- No greetings, no 'I would be happy to help'.\n"
    "- Bullet lists: max 5 items. Tables only when truly tabular.\n"
    "- One short question instead of guessing.\n"
    "- Use ## headings to structure longer answers.\n\n"
    "## Tool selection (use ONLY these)\n"
    "Read-only tasks (find bugs, list files, read code): "
    "`read_file`, `list_files`, `search_files`, `repo_search`, "
    "`repo_scan`. NEVER use mutating tools for read-only questions.\n\n"
    "Shell-out for read is BANNED - do not call `python -c`, `sed`, `awk`, "
    "`cat`, `head`, `tail`, `grep`, `rg`, `find` for reading. Use the "
    "eaccode tools above.\n\n"
    "`run_command` is for builds/tests/installs: `pytest`, `npm test`, "
    "`git status`, `node x.js`, `python x.py`, `./node_modules/.bin/tsc`. "
    "Not for `cat`, `ls`, `pwd`. Not for `python -c '...'` when a "
    "dedicated tool exists.\n\n"
    "Mutating tools (`write_file`, `file_edit`, `patch_file`, "
    "`patch_multiple`, `run_command` with side effects) are ONLY for "
    "tasks that explicitly ask for changes.\n\n"
    "`undo_edit` rolls back the most recent writes. NEVER call it for "
    "read-only questions like 'show me the code' or 'find a bug'.\n\n"
    "## Workflow\n"
    "- 'show me X' -> read_file (with offset/limit for large files). "
    "Do not paste the whole file in chat.\n"
    "- 'find bugs' -> read_file targeted + search_files + summarize.\n"
    "- 'fix X' -> file_edit the file, then run_command to verify.\n"
    "- 'list dir' / 'what is on desktop' -> list_files.\n\n"
    "## Workspace, sandbox, approvals\n"
    "The cwd is the workspace root. All file tools are sandboxed to it.\n"
    "For paths outside cwd use `/approvals allow-path PATH --session` "
    "first.\n\n"
    "Always end a turn with a clear status: what changed, what is left, "
    "what (if anything) needs user input."
)

# Defaults - all of these are overridable via config.yaml or Agent(...)
DEFAULT_MAX_TURNS = 50
DEFAULT_MAX_OUTPUT_TOKENS = 4096
# Legacy names - kept for back-compat with any external callers
MAX_TURNS = DEFAULT_MAX_TURNS
MAX_OUTPUT_TOKENS = DEFAULT_MAX_OUTPUT_TOKENS


# Re-export for back-compat with tests/internal callers
from eaccode.providers.base import StreamChunk, ToolCall  # noqa: E402,F401


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




def _shorten_for_display(value: object, max_len: int = 120) -> str:
    """Format a value for terminal display, truncated and stringified."""
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _shorten_args_for_display(args: dict[str, object], max_len: int = 80) -> dict[str, object]:
    """Truncate each arg's value for safe display (Plan K K.2).

    Preserves the original type when the stringified value fits;
    only stringifies-and-truncates when over the limit.
    """
    out: dict[str, object] = {}
    for k, v in args.items():
        s = str(v)
        if len(s) <= max_len:
            out[k] = v  # keep original type
        else:
            out[k] = s[: max_len - 3] + "..."
    return out

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
        max_turns: int | None = None,
        max_output_tokens: int | None = None,
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
        # Configurable budgets (Plan I P0.3):
        # - explicit kwarg wins
        # - then config.yaml ``agent.max_turns`` / ``agent.max_output_tokens``
        # - then DEFAULT_MAX_TURNS / DEFAULT_MAX_OUTPUT_TOKENS
        agent_cfg = self.conf.get("agent") or {}
        self.max_turns = (
            max_turns
            if max_turns is not None
            else agent_cfg.get("max_turns", DEFAULT_MAX_TURNS)
        )
        self.max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else agent_cfg.get("max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)
        )

    def _max_tokens_for(self, model_id: str) -> int:
        """Pick max_tokens from models.dev, fall back to self.max_output_tokens.

        Always returns a positive int (never None) so range(int) works.
        """
        provider_name, _, model_short = model_id.partition("/")
        try:
            md = models_dev.get_max_output_tokens(provider_name, model_short)
        except Exception:
            md = 0
        result = md or self.max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS
        if not isinstance(result, int) or result <= 0:
            return DEFAULT_MAX_OUTPUT_TOKENS
        return result

    def _complete(
        self,
        messages: list[dict[str, Any]],
        max_output_tokens: int,
        on_token: Any = None,
        on_chunk: Any | None = None,
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
            # Plan L L.4: sort manifest so read-only tools come first.
            from eaccode.tools import sorted_for_manifest
            ordered = sorted_for_manifest(list(self.tools.values())) if self.tools else []
            tool_schemas = (
                [_tool_schema(tool) for tool in ordered]
                if ordered
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
                if on_chunk is not None:
                    on_chunk(chunk)
            elif chunk.kind == "reasoning" and chunk.content:
                reasoning_parts.append(chunk.content)
                if on_token is not None:
                    _safe_on_token(on_token, chunk)
                if on_chunk is not None:
                    on_chunk(chunk)
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

    def _context_window_for(self, model_id: str) -> int:
        """Return the model's context window in tokens. Fallback 32k."""
        try:
            provider_name, _, model_short = model_id.partition("/")
            from eaccode.models_dev import get_max_input_tokens
            return get_max_input_tokens(provider_name, model_short) or 32_000
        except Exception:
            return 32_000

    def _maybe_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compact history if it exceeds 80% of the model's context window."""
        try:
            _, _, model_id = _state_to_provider(self.conf)
            window = self._context_window_for(model_id)
        except Exception:
            window = 32_000

        tool_defs = []
        for tool in self.tools.values():
            tool_defs.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            })

        if not compactor.should_compact(messages, tool_defs, window, threshold=0.8):
            return messages

        to_compact, to_keep = compactor.select_compaction_window(messages, keep_recent=4)
        if not to_compact:
            return messages

        transcript = compactor.format_messages_for_summary(to_compact)
        summary_prompt = compactor.summarize_prompt(transcript)
        try:
            content, _ = self._complete(summary_prompt, max_output_tokens=512, tools=[])
            if not content:
                return messages
            summary_msg = compactor.make_summary_message(content)
        except Exception:
            return messages

        return [summary_msg] + to_keep

    def run(
        self,
        messages: list[dict[str, str]],
        max_turns: int = MAX_TURNS,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
        cancel_event: Any | None = None,
        on_token: Any = None,
        on_chunk: Any | None = None,
        session_key: str | None = None,
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
                history, max_output_tokens,
                on_token=on_token,
                on_chunk=on_chunk,
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
            # Plan K K.2: emit tool_start before each call, tool_end after.
            # Wrap _execute_tool to capture timing + result + error.
            def _invoke_with_events(call: ToolCall) -> str:
                if on_chunk is not None:
                    on_chunk(StreamChunk(
                        kind="tool_start",
                        tool_name=call.name,
                        tool_args=_shorten_args_for_display(call.arguments),
                    ))
                start = time.monotonic()
                try:
                    result = self._execute_tool(call)
                except Exception as exc:
                    duration_ms = int((time.monotonic() - start) * 1000)
                    if on_chunk is not None:
                        on_chunk(StreamChunk(
                            kind="tool_error",
                            tool_name=call.name,
                            tool_error=str(exc),
                            tool_duration_ms=duration_ms,
                        ))
                    return f"Error: tool {call.name} failed: {exc}"
                duration_ms = int((time.monotonic() - start) * 1000)
                if on_chunk is not None:
                    on_chunk(StreamChunk(
                        kind="tool_end",
                        tool_name=call.name,
                        tool_result=_shorten_for_display(result, max_len=200),
                        tool_duration_ms=duration_ms,
                    ))
                return result

            if len(calls) > 1:
                workers = min(len(calls), 6)
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    results = list(pool.map(_invoke_with_events, calls))
            else:
                results = [_invoke_with_events(calls[0])]
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
