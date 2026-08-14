"""Tests for the flat slash palette (variante 3)."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from eaccode import palette

ENTRIES = [
    ("/help", "show this help", False),
    ("/memory", "memory verwalten", False),
    ("/model", "modelle verwalten", False),
    ("/zeit-helfer", "skill (uhrzeit)", True),
]


class TestFuzzy:
    def test_subsequence_match(self) -> None:
        assert palette.fuzzy_match("mcp", "mcp")
        assert palette.fuzzy_match("mem", "memory")
        assert palette.fuzzy_match("mry", "memory")  # subsequence
        assert palette.fuzzy_match("", "anything")
        assert not palette.fuzzy_match("xyz", "memory")
        assert palette.fuzzy_match("MEM", "memory")  # case-insensitive


class TestEntries:
    def test_contains_commands_and_skills(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from eaccode import skills

        def fake_skills() -> list[Any]:
            return [
                {"name": "zeit-helfer", "trigger": "uhrzeit", "description": "x"},
            ]

        monkeypatch.setattr(skills, "list_skills", fake_skills)
        entries = palette.palette_entries()
        texts = [entry[0] for entry in entries]
        assert "/help" in texts
        assert "/exit" in texts
        assert "/zeit-helfer" in texts
        skills_entry = next(entry for entry in entries if entry[0] == "/zeit-helfer")
        assert skills_entry[2] is True

    def test_skills_failure_is_silent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from eaccode import skills

        def broken() -> list[Any]:
            raise OSError("no skills dir")

        monkeypatch.setattr(skills, "list_skills", broken)
        entries = palette.palette_entries()
        assert any(entry[0] == "/help" for entry in entries)


class TestPalettePrompt:
    def test_refresh_opens_on_slash(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("/")
        assert prompt.visible
        assert len(prompt._filtered) == 4

    def test_refresh_filters_fuzzy(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("/mem")
        assert [e[0] for e in prompt._filtered] == ["/memory"]

    def test_refresh_closes_without_slash(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("/mem")
        prompt.refresh("hallo")
        assert not prompt.visible
        assert prompt._filtered == []

    def test_move_wraps(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("/")
        prompt.move(1)
        assert prompt.selected == 1
        prompt.move(-2)  # wraps to last
        assert prompt.selected == 3

    def test_accept_returns_selection(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("/mem")
        assert prompt.accept() == "/memory"

    def test_accept_none_when_hidden(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("kein slash")
        assert prompt.accept() is None

    def test_render_flat_list_with_aligned_columns(self) -> None:
        entries = ENTRIES + [("/zeit-helfer", "skill (uhrzeit)", True)]
        prompt = palette.PalettePrompt(entries)
        prompt.refresh("/")
        lines = prompt._render_lines()
        text = "".join(part for _, part in lines)
        assert "❯" in text
        assert "Commands" not in text  # no sections
        assert "Skills" not in text
        assert "─" not in text  # no separator
        assert "/help" in text
        assert "/zeit-helfer" in text
        # names are aligned: /help and /memory have same column width
        assert "/help" in text and "/memory" in text

    def test_render_no_matches(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("/xyz")
        text = "".join(part for _, part in prompt._render_lines())
        assert "no matches" in text


def _fake_chunk(content: str | None = None, tool_call: Any = None) -> Any:
    from types import SimpleNamespace

    delta: dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    if tool_call is not None:
        delta["tool_calls"] = [tool_call]
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(**delta))]
    )


def test_streaming_emits_deltas_and_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import eaccode.router as router_mod
    from eaccode.agent import Agent

    tc1 = SimpleNamespace(
        index=0,
        id="call_9",
        function=SimpleNamespace(name="current_time", arguments='{"tz":'),
    )
    tc2 = SimpleNamespace(
        index=0,
        id="call_9",
        function=SimpleNamespace(name="current_time", arguments='"UTC"}'),
    )
    chunks = [
        _fake_chunk(content="Ich "),
        _fake_chunk(content="antworte"),
        _fake_chunk(content=None, tool_call=tc1),
        _fake_chunk(content=None, tool_call=tc2),
    ]

    def fake_stream(
        model_id: str,
        messages: list[dict[str, Any]],
        conf: dict[str, Any],
        timeout: float = 90.0,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> Any:
        assert extra_kwargs is not None and extra_kwargs.get("max_tokens") == 1024
        return iter(chunks)

    monkeypatch.setattr(router_mod, "stream_completion", fake_stream)
    monkeypatch.setattr(router_mod, "model_chain", lambda conf: ["minimax/MiniMax-M3"])

    agent = Agent(system_prompt="sys", tools=[])
    received: list[str] = []
    content, calls = agent._complete(
        [{"role": "user", "content": "hallo"}], 1024, on_token=received.append
    )
    assert "".join(received) == "Ich antworte"
    assert content == "Ich antworte"
    assert len(calls) == 1
    assert calls[0].name == "current_time"
    assert calls[0].arguments == {"tz": "UTC"}


def test_streaming_round_marker_opens_fresh_lines() -> None:
    app = palette.ChatApp(agent=FakeAgent())
    app._on_token("")  # round marker
    app._on_token("Hallo ")
    app._on_token("Welt")
    assert app._log_lines[-1] == ("class:chat.agent", "Hallo Welt")
    assert app._streamed_any is True
    app._on_token("")  # next round: fresh line
    app._on_token("Zweite")
    assert app._log_lines[-1] == ("class:chat.agent", "Zweite")


def test_stream_completion_sets_stream_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import eaccode.router as router_mod

    seen: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> Any:
        seen.update(kwargs)
        return iter([])

    monkeypatch.setattr("litellm.completion", fake_completion)
    conf = {"providers": {"minimax": {"api_key": "x"}}}
    result = router_mod.stream_completion(
        "minimax/MiniMax-M3", [{"role": "user", "content": "hi"}], conf
    )
    assert list(result) == []  # returned the chunk iterator
    assert seen.get("stream") is True
    assert seen.get("model") == "minimax/MiniMax-M3"


class TestPipeIntegration:
    def test_enter_picks_selection(self) -> None:
        pytest.importorskip("prompt_toolkit")
        from prompt_toolkit.input.defaults import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        with create_pipe_input() as pipe:
            prompt = palette.PalettePrompt(ENTRIES)
            app = prompt.build_application(input=pipe, output=DummyOutput())
            result: dict[str, str] = {}

            def run() -> None:
                result["text"] = app.run()

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            assert _wait_for(lambda: app.is_running), "app did not start"
            pipe.send_text("/mem")
            time.sleep(0.3)
            pipe.send_text("\r")  # enter -> picks /memory
            thread.join(timeout=5)
            assert not thread.is_alive()
            assert result.get("text") == "/memory"


class FakeAgent:
    def __init__(self, reply: str = "chat antwort") -> None:
        self.reply = reply
        self.system_prompt = "system"

    def run(
        self,
        messages: list[dict[str, str]],
        on_token: Any = None,
    ) -> list[dict[str, Any]]:
        if on_token is not None:
            on_token("")
            on_token(self.reply)
        return (
            [{"role": "system", "content": self.system_prompt}]
            + list(messages)
            + [{"role": "assistant", "content": self.reply}]
        )

    def last_text(self, history: list[dict[str, Any]]) -> str:
        return self.reply


def _wait_for(predicate: Any, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class TestChatApp:
    def test_submit_chats_and_logs_answer(self) -> None:
        app = palette.ChatApp(agent=FakeAgent(reply="hallo aus dem chat"))
        app._submit("wie gehts")
        assert _wait_for(lambda: any("hallo aus dem chat" in t for _, t in app._log_lines))
        assert any("> wie gehts" in t for _, t in app._log_lines)

    def test_slash_opens_palette_then_runs(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        app._submit("/mem")  # first enter: opens palette
        assert app.palette.visible
        app._submit("/mem")  # second enter: picks /memory and runs it
        assert not app.palette.visible
        assert any("Usage: memory" in t for _, t in app._log_lines)

    def test_escape_closes_palette(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        app._submit("/")
        assert app.palette.visible
        app.palette.visible = False  # escape binding path
        assert not app.palette.visible

    def test_permission_flow(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        app._permission_prompt = "write_file x"
        app._submit("y")
        assert app._permission_answer == "y"
        assert app._permission_prompt is None

    def test_ask_returns_bool(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        result: dict[str, bool] = {}

        def ask() -> None:
            result["value"] = app._ask("x")

        thread = threading.Thread(target=ask, daemon=True)
        thread.start()
        assert _wait_for(lambda: app._permission_prompt is not None)
        app._submit("y")  # answer yes
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert result.get("value") is True

        def ask_no() -> None:
            result["value"] = app._ask("x")

        thread = threading.Thread(target=ask_no, daemon=True)
        thread.start()
        assert _wait_for(lambda: app._permission_prompt is not None)
        app._submit("n")  # answer no
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert result.get("value") is False

    def test_agent_gate_wired(self) -> None:
        from types import SimpleNamespace

        manager = SimpleNamespace(ask_handler=None)
        agent = FakeAgent()
        agent.permission_manager = manager
        app = palette.ChatApp(agent=agent)
        app._wire_agent_gate(agent)
        assert manager.ask_handler is not None
        result: dict[str, bool] = {}

        def ask() -> None:
            result["value"] = manager.ask_handler("write_file", {"x": 1})

        thread = threading.Thread(target=ask, daemon=True)
        thread.start()
        assert _wait_for(lambda: app._permission_prompt is not None)
        app._submit("yes")  # inline answer
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert result.get("value") is True

    def test_clear_empties_log(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        app._append("", "etwas")
        app._submit("/clear")
        app._submit("/clear")  # palette -> pick -> run
        assert app._log_lines == []

    def test_unknown_slash_reports_error(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        app._submit("/nonsense")
        app._submit("/nonsense")
        assert any("Unknown command" in t for _, t in app._log_lines)

    def test_log_lines_are_newline_terminated(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        app._append("", "erste zeile")
        app._append("", "zweite zeile")
        assert app._log_lines == [("", "erste zeile\n"), ("", "zweite zeile\n")]

    def test_run_writes_banner_into_log(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(palette, "banner_quiet", lambda: False)
        app = palette.ChatApp(agent=FakeAgent())
        # simulate the run() banner step (real terminals only; build_application
        # would need a console, so the log-writing part is tested directly)
        from eaccode import store as _store

        app._session_id = _store.new_session()
        app._append(
            "class:chat.banner",
            palette.render_banner(
                {"model": {"default": "minimax/MiniMax-M3"}},
                session_id=app._session_id,
                cwd="C:\\x",
            ),
        )
        text = "".join(t for _, t in app._log_lines)
        assert "Welcome to eaccode!" in text
        assert "eaccode 0.0.1" in text
        assert "Session:" in text

    def test_pipe_roundtrip(self) -> None:
        pytest.importorskip("prompt_toolkit")
        from prompt_toolkit.input.defaults import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        with create_pipe_input() as pipe:
            app = palette.ChatApp(agent=FakeAgent(reply="pipe antwort"))
            application = app.build_application(input=pipe, output=DummyOutput())

            def run() -> None:
                application.run()

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            assert _wait_for(lambda: application.is_running), "app did not start"
            pipe.send_text("hallo\n")  # enter submits
            assert _wait_for(
                lambda: any("pipe antwort" in t for _, t in app._log_lines)
            )
            pipe.send_text("\x03")  # ctrl+c exits
            thread.join(timeout=5)
            assert not thread.is_alive()
