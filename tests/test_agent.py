"""Tests for the agent core loop (Phase A4, B1 skill injection)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from eaccode import config as cfg
from eaccode import router
from eaccode.agent import Agent, Tool, ToolCall, parse_response


def _conf() -> dict[str, Any]:
    return cfg.defaults() | {"model": {"default": "openrouter/test", "fallback": []}}


def _message(
    content: str | None, tool_calls: list[dict[str, Any]] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _response(
    content: str | None, tool_calls: list[dict[str, Any]] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=_message(content, tool_calls))])


def _tool_call_raw(call_id: str, name: str, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=arguments)
    )


class TestParseResponse:
    def test_plain_content(self) -> None:
        content, calls = parse_response(_response("hello"))
        assert content == "hello"
        assert calls == []

    def test_tool_calls_parsed(self) -> None:
        content, calls = parse_response(
            _response(
                None,
                [_tool_call_raw("c1", "echo", '{"text": "hi"}')],
            )
        )
        assert content is None
        assert calls == [ToolCall(id="c1", name="echo", arguments={"text": "hi"})]

    def test_bad_json_arguments_become_empty_dict(self) -> None:
        _, calls = parse_response(_response(None, [_tool_call_raw("c1", "x", "not json")]))
        assert calls[0].arguments == {}

    def test_missing_id_gets_fallback(self) -> None:
        raw = SimpleNamespace(id=None, function=SimpleNamespace(name="x", arguments="{}"))
        _, calls = parse_response(_response(None, [raw]))
        assert calls[0].id == "call_0"


class TestAgentLoop:
    def test_single_answer_no_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        monkeypatch.setattr(litellm, "completion", lambda **kw: _response("hi there"))
        agent = Agent(conf=_conf())
        history = agent.run([{"role": "user", "content": "say hi"}])
        assert history[-1]["role"] == "assistant"
        assert history[-1]["content"] == "hi there"
        assert agent.last_text(history) == "hi there"

    def test_tool_executed_and_result_fed_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            calls.append(kwargs["messages"][-1]["role"])
            if len(calls) == 1:
                return _response(None, [_tool_call_raw("c1", "echo", '{"text": "ping"}')])
            return _response("done")

        echo = Tool(
            name="echo",
            description="echo text back",
            func=lambda text: f"echo:{text}",
        )
        import litellm

        monkeypatch.setattr(litellm, "completion", fake_completion)
        agent = Agent(conf=_conf(), tools=[echo])
        history = agent.run([{"role": "user", "content": "use echo"}])
        roles = [m["role"] for m in history]
        assert roles == ["system", "user", "assistant", "tool", "assistant"]
        assert history[-2]["role"] == "tool"
        assert history[-2]["content"] == "echo:ping"
        assert history[-2]["tool_call_id"] == "c1"
        assert agent.last_text(history) == "done"

    def test_unknown_tool_returns_error_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            if kwargs["messages"][-1]["role"] == "tool":
                return _response("ok")
            return _response(None, [_tool_call_raw("c1", "ghost", "{}")])

        monkeypatch.setattr(litellm, "completion", fake_completion)
        agent = Agent(conf=_conf())
        history = agent.run([{"role": "user", "content": "x"}])
        tool_message = next(m for m in history if m["role"] == "tool")
        assert "unknown tool: ghost" in tool_message["content"]

    def test_tool_exception_does_not_kill_loop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        def boom() -> None:
            raise RuntimeError("kaputt")

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            if kwargs["messages"][-1]["role"] == "tool":
                return _response("ok")
            return _response(None, [_tool_call_raw("c1", "bad", "{}")])

        monkeypatch.setattr(litellm, "completion", fake_completion)
        agent = Agent(conf=_conf(), tools=[Tool(name="bad", description="x", func=boom)])
        history = agent.run([{"role": "user", "content": "x"}])
        tool_message = next(m for m in history if m["role"] == "tool")
        assert "kaputt" in tool_message["content"]

    def test_max_turns_stops_with_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            return _response(None, [_tool_call_raw("c1", "echo", '{"text": "x"}')])

        echo = Tool(name="echo", description="echo", func=lambda text: text)
        monkeypatch.setattr(litellm, "completion", fake_completion)
        agent = Agent(conf=_conf(), tools=[echo])
        history = agent.run([{"role": "user", "content": "x"}], max_turns=2)
        assert "max turns" in agent.last_text(history)

    def test_no_default_model_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        monkeypatch.setattr(litellm, "completion", lambda **kw: _response("x"))
        conf = cfg.defaults() | {"model": {"default": "", "fallback": []}}
        agent = Agent(conf=conf)
        with pytest.raises(router.ModelError, match="model set-default"):
            agent.run([{"role": "user", "content": "x"}])

    def test_tools_sent_in_first_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            captured.update(kwargs)
            return _response("ok")

        import litellm

        monkeypatch.setattr(litellm, "completion", fake_completion)
        agent = Agent(
            conf=_conf(),
            tools=[Tool(name="echo", description="echoes", func=lambda text: text)],
        )
        agent.run([{"role": "user", "content": "x"}])
        assert "tools" in captured
        schema = captured["tools"][0]
        assert schema["function"]["name"] == "echo"
        assert captured["tool_choice"] == "auto"

    def test_tool_arguments_json_roundtrip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        received: dict[str, Any] = {}

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            if kwargs["messages"][-1]["role"] == "tool":
                received["tool_msg"] = kwargs["messages"][-1]
                return _response("ok")
            return _response(
                None,
                [
                    _tool_call_raw(
                        "c9",
                        "record",
                        json.dumps({"a": 1, "b": ["x", "y"]}),
                    )
                ],
            )

        def record(a: int, b: list[str]) -> str:
            return "recorded"

        import litellm

        monkeypatch.setattr(litellm, "completion", fake_completion)
        agent = Agent(conf=_conf(), tools=[Tool(name="record", description="r", func=record)])
        agent.run([{"role": "user", "content": "go"}])
        tool_msg = received["tool_msg"]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "c9"


class TestSkillInjection:
    def test_matching_skill_injected_into_system_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import litellm

        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            litellm, "completion", lambda **kw: captured.update(kw) or _response("ok")
        )
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        from eaccode import skills as skill_mod

        skill_mod.create_skill("zeit", "time helper", "uhrzeit", body="Nutze current_time!")
        agent = Agent(conf=_conf(), use_skills=True)
        agent.run([{"role": "user", "content": "Wie spät? UHRZEIT bitte"}])
        system = captured["messages"][0]["content"]
        assert "## Relevant skills" in system
        assert "Nutze current_time!" in system

    def test_no_match_keeps_prompt_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import litellm

        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            litellm, "completion", lambda **kw: captured.update(kw) or _response("ok")
        )
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        from eaccode import skills as skill_mod

        skill_mod.create_skill("zeit", "time helper", "uhrzeit")
        agent = Agent(conf=_conf(), use_skills=True)
        agent.run([{"role": "user", "content": "irgendwas ganz anderes"}])
        assert "Relevant skills" not in captured["messages"][0]["content"]

    def test_use_skills_false_disables_injection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import litellm

        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            litellm, "completion", lambda **kw: captured.update(kw) or _response("ok")
        )
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        from eaccode import skills as skill_mod

        skill_mod.create_skill("zeit", "time helper", "uhrzeit")
        agent = Agent(conf=_conf(), use_skills=False)
        agent.run([{"role": "user", "content": "UHRZEIT"}])
        assert "Relevant skills" not in captured["messages"][0]["content"]


class TestParallelTools:
    def test_two_calls_run_concurrently(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import time

        import litellm

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            if kwargs["messages"][-1]["role"] == "tool":
                return _response("fertig")
            return _response(
                None,
                [
                    _tool_call_raw("c1", "slow", '{"tag": "a"}'),
                    _tool_call_raw("c2", "slow", '{"tag": "b"}'),
                ],
            )

        def slow(tag: str) -> str:
            time.sleep(0.4)
            return tag

        monkeypatch.setattr(litellm, "completion", fake_completion)
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

        import litellm

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            if kwargs["messages"][-1]["role"] == "tool":
                return _response("fertig")
            return _response(
                None,
                [
                    _tool_call_raw("c1", "boom", "{}"),
                    _tool_call_raw("c2", "slow", '{"tag": "ok"}'),
                ],
            )

        def boom() -> str:
            raise RuntimeError("kaputt")

        def slow(tag: str) -> str:
            time.sleep(0.2)
            return tag

        monkeypatch.setattr(litellm, "completion", fake_completion)
        agent = Agent(
            conf=_conf(),
            tools=[
                Tool(name="boom", description="b", func=boom),
                Tool(name="slow", description="s", func=slow),
            ],
        )
        history = agent.run([{"role": "user", "content": "isoliere!"}])
        tool_messages = [m for m in history if m["role"] == "tool"]
        contents = [m["content"] for m in tool_messages]
        assert any("kaputt" in c for c in contents)  # failed tool reported
        assert any("ok" in c for c in contents)  # other tool still ran
        assert agent.last_text(history) == "fertig"  # loop survived


class TestCancelEvent:
    def test_cancel_stops_loop_cleanly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import threading

        import litellm

        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            litellm, "completion", lambda **kw: captured.update(kw) or _response("ok")
        )
        agent = Agent(conf=_conf())
        cancel = threading.Event()
        cancel.set()
        history = agent.run(
            [{"role": "user", "content": "hallo"}], cancel_event=cancel
        )
        assert agent.last_text(history) == "(cancelled by timeout guard)"
        assert len(history) == 3  # system + user + cancellation note
        assert "messages" not in captured  # no model call happened


class TestMemoryNudge:
    def test_nudge_appears_every_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        captured: dict[str, Any] = {}
        monkeypatch.setattr(
            litellm, "completion", lambda **kw: captured.update(kw) or _response("ok")
        )
        agent = Agent(conf=_conf(), memory_nudge_interval=2)
        agent.run([{"role": "user", "content": "eins"}])
        assert "Memory nudge" not in captured["messages"][0]["content"]
        agent.run([{"role": "user", "content": "zwei"}])
        assert "Memory nudge" in captured["messages"][0]["content"]

    def test_memory_tool_call_resets_nudge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        captured: dict[str, Any] = {}

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            captured["messages"] = kwargs["messages"]
            if kwargs["messages"][-1]["role"] == "tool":
                return _response("ok")
            return _response(
                None,
                [
                    _tool_call_raw(
                        "c1", "memory_add", '{"target": "agent", "content": "fakt"}'
                    )
                ],
            )

        monkeypatch.setattr(litellm, "completion", fake_completion)

        def memory_add(target: str, content: str) -> str:
            return "ok"

        agent = Agent(
            conf=_conf(),
            memory_nudge_interval=2,
            tools=[Tool(name="memory_add", description="m", func=memory_add)],
        )
        agent.run([{"role": "user", "content": "eins"}])  # tool call resets counter
        agent.run([{"role": "user", "content": "zwei"}])
        agent.run([{"role": "user", "content": "drei"}])
        system = captured["messages"][0]["content"]
        assert "Memory nudge" not in system  # counter was reset by the tool call
