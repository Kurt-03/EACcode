"""Tests for the agent core loop.

Each test uses a `FakeProvider` (subclass of eaccode.providers.base.Provider)
that yields a fixed sequence of StreamChunks. The agent does not care
about Anthropic-specific events — only the StreamChunk contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from eaccode import config as cfg
from eaccode import permissions
from eaccode.agent import Agent, Tool, ToolCall
from eaccode.providers import registry as provider_registry
from eaccode.providers.base import StreamChunk


def _conf() -> dict[str, Any]:
    return cfg.defaults() | {
        "model": {"default": "anthropic/test-model", "fallback": []},
        "providers": {
            "anthropic": {"api_key": "sk-test"},
        },
    }


class FakeProvider:
    """Provider that yields a fixed sequence of StreamChunks per call."""

    def __init__(self, responses: list[list[StreamChunk]] | list[StreamChunk]) -> None:
        if responses and not isinstance(responses[0], list):
            responses = [responses]  # type: ignore[list-item]
        self.responses: list[list[StreamChunk]] = responses  # type: ignore[assignment]
        self.call_count = 0
        self.last_kwargs: dict[str, Any] = {}

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        cancel_event: Any | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Any:

        self.last_kwargs = {
            "messages": messages,
            "system": system,
            "tools": tools,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        response = (
            self.responses[self.call_count]
            if self.call_count < len(self.responses)
            else []
        )
        self.call_count += 1
        return iter(response)


def _tool_call_chunk(call_id: str, name: str, args: dict[str, Any]) -> StreamChunk:
    return StreamChunk(
        kind="tool_call",
        tool_call=ToolCall(id=call_id, name=name, arguments=args),
    )


def _text(text: str) -> StreamChunk:
    return StreamChunk(kind="text", content=text)


def _reasoning(text: str) -> StreamChunk:
    return StreamChunk(kind="reasoning", content=text)


def _done() -> StreamChunk:
    return StreamChunk(kind="done")


@pytest.fixture(autouse=True)
def reset_provider_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset provider cache and stub out the registry.get to use FakeProvider."""
    import sys as _sys
    provider_registry.reset_cache()
    # Patch anthropic SDK so the registry build doesn't actually call out
    fake_anthropic = MagicMock()
    monkeypatch.setitem(_sys.modules, "anthropic", fake_anthropic)
    yield
    provider_registry.reset_cache()


def _patch_provider(monkeypatch: pytest.MonkeyPatch, fake: FakeProvider) -> None:
    """Patch `provider_registry.get` to return a FakeProvider without anthropic SDK."""

    def fake_get(
        provider_name: str,
        provider_config: dict[str, Any],
        *,
        model: str = "",
        timeout: float = 60.0,
    ) -> FakeProvider:
        return fake

    monkeypatch.setattr(provider_registry, "get", fake_get)


def _tool(name: str, description: str) -> Tool:
    return Tool(name, description, func=lambda **_: "")


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------


def test_tool_guide_lists_tools_and_flow() -> None:
    from eaccode.agent import tool_guide

    guide = tool_guide(
        {
            "read_file": _tool("read_file", "Read a file"),
            "run_tests": _tool("run_tests", "Run the test suite"),
            "repo_scan": _tool("repo_scan", "Index a repository"),
        }
    )
    assert "read_file" in guide
    assert "Read a file" in guide
    assert "run_tests" in guide
    assert "repo_scan" in guide
    assert "Typical coding flow" in guide
    assert "git_commit" in guide


def test_agent_prompt_contains_tool_guide() -> None:
    agent = Agent(
        system_prompt="base prompt",
        tools=[
            _tool("read_file", "Read a file"),
            _tool("run_tests", "Run the test suite"),
        ],
    )
    assert "## Available tools" in agent.system_prompt
    assert "read_file" in agent.system_prompt
    assert "Typical coding flow" in agent.system_prompt


def test_agent_without_tools_keeps_prompt() -> None:
    agent = Agent(system_prompt="base prompt", tools=[])
    assert agent.system_prompt == "base prompt"


# ---------------------------------------------------------------------------
# _max_tokens_for
# ---------------------------------------------------------------------------


class TestMaxTokens:
    def test_max_tokens_uses_models_dev_when_known(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from eaccode import models_dev

        monkeypatch.setattr(
            models_dev, "get_max_output_tokens", lambda *a, **kw: 131072
        )
        agent = Agent(conf=_conf())
        assert agent._max_tokens_for("anthropic/test-model") == 131072

    def test_max_tokens_falls_back_to_default_when_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from eaccode import models_dev

        monkeypatch.setattr(models_dev, "get_max_output_tokens", lambda *a, **kw: 0)
        agent = Agent(conf=_conf())
        assert agent._max_tokens_for("anthropic/unknown") == 1024


# ---------------------------------------------------------------------------
# Agent.run — single answer
# ---------------------------------------------------------------------------


class TestAgentRun:
    def test_single_answer_no_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider([[_text("hi there"), _done()]])
        _patch_provider(monkeypatch, fake)
        agent = Agent(conf=_conf())
        history = agent.run([{"role": "user", "content": "say hi"}])
        assert history[-1]["role"] == "assistant"
        assert history[-1]["content"] == "hi there"
        assert agent.last_text(history) == "hi there"

    def test_streaming_deltas_accumulate_into_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake = FakeProvider(
            [
                [
                    _text("Hello "),
                    _text("world"),
                    _text("!"),
                    _done(),
                ]
            ]
        )
        _patch_provider(monkeypatch, fake)
        agent = Agent(conf=_conf())
        history = agent.run([{"role": "user", "content": "hi"}])
        assert history[-1]["content"] == "Hello world!"

    def test_no_default_model_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider([])
        _patch_provider(monkeypatch, fake)
        conf = cfg.defaults() | {"model": {"default": "", "fallback": []}}
        agent = Agent(conf=conf)
        with pytest.raises(Exception, match="model set-default"):
            agent.run([{"role": "user", "content": "x"}])

    def test_tools_sent_in_first_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider([[_text("ok"), _done()]])
        _patch_provider(monkeypatch, fake)
        agent = Agent(
            conf=_conf(),
            tools=[Tool(name="echo", description="echoes", func=lambda text: text)],
        )
        agent.run([{"role": "user", "content": "x"}])
        assert fake.last_kwargs["tools"] is not None
        schema = fake.last_kwargs["tools"][0]
        assert schema["function"]["name"] == "echo"
        assert schema["function"]["parameters"]["type"] == "object"


# ---------------------------------------------------------------------------
# Agent.run — tool calls
# ---------------------------------------------------------------------------


class TestToolCalls:
    def test_tool_executed_and_result_fed_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider(
            [
                # First turn: tool call
                [_tool_call_chunk("c1", "echo", {"text": "ping"}), _done()],
                # Second turn: final answer
                [_text("done"), _done()],
            ]
        )
        _patch_provider(monkeypatch, fake)

        echo = Tool(
            name="echo",
            description="echo text back",
            func=lambda text: f"echo:{text}",
        )
        agent = Agent(conf=_conf(), tools=[echo])
        history = agent.run([{"role": "user", "content": "use echo"}])
        roles = [m["role"] for m in history]
        assert roles == ["system", "user", "assistant", "tool", "assistant"]
        tool_msg = next(m for m in history if m["role"] == "tool")
        assert tool_msg["content"] == "echo:ping"
        assert tool_msg["tool_call_id"] == "c1"
        assert agent.last_text(history) == "done"

    def test_unknown_tool_returns_error_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider(
            [
                [_tool_call_chunk("c1", "ghost", {}), _done()],
                [_text("ok"), _done()],
            ]
        )
        _patch_provider(monkeypatch, fake)
        agent = Agent(conf=_conf())
        history = agent.run([{"role": "user", "content": "x"}])
        tool_msg = next(m for m in history if m["role"] == "tool")
        assert "unknown tool: ghost" in tool_msg["content"]

    def test_tool_exception_does_not_kill_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider(
            [
                [_tool_call_chunk("c1", "bad", {}), _done()],
                [_text("ok"), _done()],
            ]
        )
        _patch_provider(monkeypatch, fake)

        def boom() -> None:
            raise RuntimeError("kaputt")

        agent = Agent(
            conf=_conf(),
            tools=[Tool(name="bad", description="x", func=boom)],
        )
        history = agent.run([{"role": "user", "content": "x"}])
        tool_msg = next(m for m in history if m["role"] == "tool")
        assert "kaputt" in tool_msg["content"]

    def test_max_turns_stops_with_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider(
            [
                [_tool_call_chunk("c1", "echo", {"text": "x"}), _done()],
                [_tool_call_chunk("c2", "echo", {"text": "y"}), _done()],
                [_tool_call_chunk("c3", "echo", {"text": "z"}), _done()],
            ]
        )
        _patch_provider(monkeypatch, fake)
        echo = Tool(name="echo", description="echo", func=lambda text: text)
        agent = Agent(conf=_conf(), tools=[echo])
        history = agent.run([{"role": "user", "content": "x"}], max_turns=2)
        assert "max turns" in agent.last_text(history)

    def test_tool_arguments_json_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        received: dict[str, Any] = {}

        class RecordingFake(FakeProvider):
            def stream(self, messages: list[dict[str, Any]], **kw: Any) -> Any:

                if messages and messages[-1].get("role") == "tool":
                    received["tool_msg"] = messages[-1]
                    return iter([_text("ok"), _done()])
                return iter(
                    [
                        _tool_call_chunk(
                            "c9", "record", {"a": 1, "b": ["x", "y"]}
                        ),
                        _done(),
                    ]
                )

        fake = RecordingFake([])
        _patch_provider(monkeypatch, fake)

        def record(a: int, b: list[str]) -> str:
            return "recorded"

        agent = Agent(
            conf=_conf(),
            tools=[Tool(name="record", description="r", func=record)],
        )
        agent.run([{"role": "user", "content": "go"}])
        assert received["tool_msg"]["role"] == "tool"
        assert received["tool_msg"]["tool_call_id"] == "c9"


# ---------------------------------------------------------------------------
# Reasoning
# ---------------------------------------------------------------------------


class TestReasoning:
    def test_reasoning_does_not_replace_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider(
            [
                [
                    _reasoning("Let me think..."),
                    _text("The answer is 42."),
                    _done(),
                ]
            ]
        )
        _patch_provider(monkeypatch, fake)
        agent = Agent(conf=_conf())
        history = agent.run([{"role": "user", "content": "q"}])
        # The assistant message carries the answer; reasoning shouldn't
        # pollute it.
        assert history[-1]["content"] == "The answer is 42."

    def test_reasoning_only_surfaces_as_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If the model only produced reasoning, surface it as the answer."""
        fake = FakeProvider([[_reasoning("All my work."), _done()]])
        _patch_provider(monkeypatch, fake)
        agent = Agent(conf=_conf())
        history = agent.run([{"role": "user", "content": "q"}])
        assert history[-1]["content"] == "All my work."


# ---------------------------------------------------------------------------
# Cancel and nudge
# ---------------------------------------------------------------------------


class TestCancelEvent:
    def test_cancel_stops_loop_cleanly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider([])
        _patch_provider(monkeypatch, fake)
        agent = Agent(conf=_conf())
        import threading

        cancel = threading.Event()
        cancel.set()
        history = agent.run(
            [{"role": "user", "content": "hallo"}], cancel_event=cancel
        )
        assert agent.last_text(history) == "(cancelled by timeout guard)"
        assert len(history) == 3  # system + user + cancellation note
        assert fake.call_count == 0  # no model call happened


class TestMemoryNudge:
    def test_nudge_appears_every_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}
        fake = FakeProvider(
            [[_text("ok"), _done()], [_text("ok2"), _done()]]
        )
        _patch_provider(monkeypatch, fake)

        # Wrap the provider to capture kwargs
        class CaptureFake(FakeProvider):
            def stream(self, messages: list[dict[str, Any]], **kw: Any) -> Any:
                captured["messages"] = messages
                return super().stream(messages, **kw)

        fake = CaptureFake(
            [[_text("ok"), _done()], [_text("ok2"), _done()]]
        )
        _patch_provider(monkeypatch, fake)

        agent = Agent(conf=_conf(), memory_nudge_interval=2)
        agent.run([{"role": "user", "content": "eins"}])
        assert "Memory nudge" not in captured["messages"][0]["content"]
        agent.run([{"role": "user", "content": "zwei"}])
        assert "Memory nudge" in captured["messages"][0]["content"]


# ---------------------------------------------------------------------------
# Parallel tool execution
# ---------------------------------------------------------------------------


class TestParallelTools:
    def test_two_calls_run_concurrently(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import time

        call_timestamps: list[float] = []

        class TimingFake(FakeProvider):
            def stream(self, messages: list[dict[str, Any]], **kw: Any) -> Any:
                if messages and messages[-1].get("role") == "tool":
                    return iter([_text("ok"), _done()])
                return iter(
                    [
                        _tool_call_chunk("c1", "slow", {"tag": "a"}),
                        _tool_call_chunk("c2", "slow", {"tag": "b"}),
                        _done(),
                    ]
                )

        fake = TimingFake([])
        _patch_provider(monkeypatch, fake)

        def slow(tag: str) -> str:
            call_timestamps.append(time.monotonic())
            time.sleep(0.4)
            return tag

        agent = Agent(
            conf=_conf(),
            tools=[Tool(name="slow", description="s", func=slow)],
        )
        start = time.monotonic()
        history = agent.run([{"role": "user", "content": "parallel!"}])
        elapsed = time.monotonic() - start
        assert elapsed < 0.7  # sequential would take ~0.8s
        assert len([m for m in history if m["role"] == "tool"]) == 2

    def test_parallel_error_isolation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import time

        class ParallelFake(FakeProvider):
            def stream(self, messages: list[dict[str, Any]], **kw: Any) -> Any:
                if messages and messages[-1].get("role") == "tool":
                    return iter([_text("fertig"), _done()])
                return iter(
                    [
                        _tool_call_chunk("c1", "boom", {}),
                        _tool_call_chunk("c2", "slow", {"tag": "ok"}),
                        _done(),
                    ]
                )

        fake = ParallelFake([])
        _patch_provider(monkeypatch, fake)

        def boom() -> str:
            raise RuntimeError("kaputt")

        def slow(tag: str) -> str:
            time.sleep(0.2)
            return tag

        agent = Agent(
            conf=_conf(),
            tools=[
                Tool(name="boom", description="b", func=boom),
                Tool(name="slow", description="s", func=slow),
            ],
        )
        history = agent.run([{"role": "user", "content": "isoliere!"}])
        contents = [m["content"] for m in history if m["role"] == "tool"]
        assert any("kaputt" in c for c in contents)
        assert any("ok" in c for c in contents)
        assert agent.last_text(history) == "fertig"


# ---------------------------------------------------------------------------
# Permission gate
# ---------------------------------------------------------------------------


class TestPermissionGate:
    def test_denied_tool_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider(
            [
                [_tool_call_chunk("c1", "write_file", {"path": "x"}), _done()],
                [_text("ok"), _done()],
            ]
        )
        _patch_provider(monkeypatch, fake)
        agent = Agent(
            conf=_conf(),
            tools=[Tool(name="write_file", description="w", func=lambda path: "ok")],
            permission_manager=permissions.PermissionManager(
                {"permissions": {"mode": "read_only", "allow": [], "deny": []}}
            ),
        )
        history = agent.run([{"role": "user", "content": "schreib!"}])
        tool_messages = [m for m in history if m["role"] == "tool"]
        assert "permission denied" in tool_messages[0]["content"]

    def test_allowed_tool_runs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = FakeProvider(
            [
                [
                    _tool_call_chunk("c1", "read_file", {"path": "x"}),
                    _done(),
                ],
                [_text("ok"), _done()],
            ]
        )
        _patch_provider(monkeypatch, fake)
        agent = Agent(
            conf=_conf(),
            tools=[
                Tool(
                    name="read_file",
                    description="r",
                    func=lambda path: "inhalt",
                )
            ],
            permission_manager=permissions.PermissionManager(
                {"permissions": {"mode": "read_only", "allow": [], "deny": []}}
            ),
        )
        history = agent.run([{"role": "user", "content": "lies!"}])
        tool_messages = [m for m in history if m["role"] == "tool"]
        assert "inhalt" in tool_messages[0]["content"]


# ---------------------------------------------------------------------------
# Skill injection
# ---------------------------------------------------------------------------


class TestSkillInjection:
    def test_matching_skill_injected_into_system_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from eaccode import skills as skill_mod

        captured_messages: list[Any] = []

        class CaptureFake(FakeProvider):
            def stream(self, messages: list[dict[str, Any]], **kw: Any) -> Any:
                captured_messages.append(messages)
                return iter([_text("ok"), _done()])

        fake = CaptureFake([])
        _patch_provider(monkeypatch, fake)

        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        skill_mod.create_skill("zeit", "time helper", "uhrzeit", body="Nutze current_time!")
        agent = Agent(conf=_conf(), use_skills=True)
        agent.run([{"role": "user", "content": "Wie spät? UHRZEIT bitte"}])
        system = captured_messages[0][0]["content"]
        assert "## Relevant skills" in system
        assert "Nutze current_time!" in system

    def test_no_match_keeps_prompt_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from eaccode import skills as skill_mod

        captured_messages: list[Any] = []

        class CaptureFake(FakeProvider):
            def stream(self, messages: list[dict[str, Any]], **kw: Any) -> Any:
                captured_messages.append(messages)
                return iter([_text("ok"), _done()])

        fake = CaptureFake([])
        _patch_provider(monkeypatch, fake)

        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        skill_mod.create_skill("zeit", "time helper", "uhrzeit")
        agent = Agent(conf=_conf(), use_skills=True)
        agent.run([{"role": "user", "content": "irgendwas ganz anderes"}])
        assert "Relevant skills" not in captured_messages[0][0]["content"]

    def test_use_skills_false_disables_injection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from eaccode import skills as skill_mod

        captured_messages: list[Any] = []

        class CaptureFake(FakeProvider):
            def stream(self, messages: list[dict[str, Any]], **kw: Any) -> Any:
                captured_messages.append(messages)
                return iter([_text("ok"), _done()])

        fake = CaptureFake([])
        _patch_provider(monkeypatch, fake)

        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        skill_mod.create_skill("zeit", "time helper", "uhrzeit")
        agent = Agent(conf=_conf(), use_skills=False)
        agent.run([{"role": "user", "content": "UHRZEIT"}])
        assert "Relevant skills" not in captured_messages[0][0]["content"]
