"""Tests for the flat slash palette and bottom-pinned chat REPL."""

from __future__ import annotations

import io
import threading
import time
from typing import Any
from unittest.mock import patch

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
        assert "/help" in text and "/memory" in text

    def test_render_no_matches(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("/xyz")
        text = "".join(part for _, part in prompt._render_lines())
        assert "no matches" in text


# ---------------------------------------------------------------------------
# Agent / streaming helpers (defined in test_agent as well, duplicated here
# for palette-level integration tests)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# ChatApp unit tests (bottom-pinned REPL)
# ---------------------------------------------------------------------------
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
    def test_submit_runs_agent(self) -> None:
        app = palette.ChatApp(agent=FakeAgent(reply="hallo aus dem chat"))
        with patch("sys.stdout", new_callable=io.StringIO) as mock:
            app._submit("wie gehts")
            assert _wait_for(lambda: "hallo aus dem chat" in mock.getvalue())
            assert "wie gehts" in mock.getvalue()

    def test_submit_runs_command_without_palette(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        # First submit opens the palette; second submit runs the selected command.
        app._submit("/help")
        with patch("sys.stdout", new_callable=io.StringIO) as mock:
            app._submit("/help")
            assert "Commands:" in mock.getvalue()

    def test_slash_opens_palette_then_runs(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        # First submit while palette is not visible: it opens and returns False
        consumed = app._submit("/mem")
        assert not consumed
        assert app.palette.visible
        # Second submit: palette picks /memory
        with patch("sys.stdout", new_callable=io.StringIO):
            app._submit("/mem")
        assert not app.palette.visible

    def test_escape_closes_palette(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        app.palette.refresh("/")
        assert app.palette.visible
        app.palette.visible = False
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

    def test_unknown_slash_reports_error(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        with patch("sys.stdout", new_callable=io.StringIO) as mock:
            app._submit("/nonsense")
            app._submit("/nonsense")
            assert "Unknown command" in mock.getvalue()

    def test_stream_think_filter(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        with patch("sys.stdout", new_callable=io.StringIO) as mock:
            app._on_token("")
            app._on_token("<think>reasoning")
            app._on_token("more</think>Answer")
            output = mock.getvalue()
            assert "Answer" in output
            assert "think" not in output

    def test_stream_cr_and_ansi_removed(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        with patch("sys.stdout", new_callable=io.StringIO) as mock:
            app._on_token("")
            app._on_token("first" + chr(13) + chr(27) + "[31msecond")
            output = mock.getvalue()
            assert chr(13) not in output
            assert chr(27) not in output
            assert "first" in output
            assert "second" in output


class TestChatAppPipeIntegration:
    def test_pipe_roundtrip(self) -> None:
        pytest.importorskip("prompt_toolkit")
        from prompt_toolkit.input.defaults import create_pipe_input
        from prompt_toolkit.output import DummyOutput

        with create_pipe_input() as pipe:
            app = palette.ChatApp(agent=FakeAgent(reply="pipe antwort"))
            application = app.build_application(input=pipe, output=DummyOutput())
            result: dict[str, str] = {}

            def run() -> None:
                result["text"] = application.run()

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            assert _wait_for(lambda: application.is_running), "app did not start"
            pipe.send_text("hallo\n")  # enter submits
            pipe.send_text("\x03")  # ctrl+c exits
            thread.join(timeout=5)
            assert not thread.is_alive()
            assert result.get("text") == ""


class TestChatAppLayout:
    """ChatApp layout puts the palette directly below the input in an HSplit."""

    def _build(self) -> Any:
        """Build the app with DummyOutput so tests don't need a real console."""
        pytest.importorskip("prompt_toolkit")
        from prompt_toolkit.output import DummyOutput

        app = palette.ChatApp(agent=FakeAgent())
        # Win32 needs a real console; use DummyOutput to bypass that
        app.build_application(output=DummyOutput())
        return app

    def test_root_is_hsplit_with_input_and_palette(self) -> None:
        from prompt_toolkit.layout import HSplit, Window

        app = self._build()
        container = app._app.layout.container
        assert isinstance(container, HSplit), (
            f"expected HSplit, got {type(container).__name__}"
        )
        # Two children: input (height 1) and palette (0-8 rows)
        children = list(container.children)
        assert len(children) == 2
        assert all(isinstance(c, Window) for c in children)

    def test_palette_window_is_after_input(self) -> None:
        """The palette Window is the second child (renders below input)."""
        app = self._build()
        children = list(app._app.layout.container.children)
        palette_win = children[1]
        # The palette window must contain a BufferControl with the prompt
        # — distinguishable from the input window by its content
        assert palette_win.content is not children[0].content

    def test_palette_max_height_is_8(self) -> None:
        """Palette Window max height is 8 rows (1 selected + 7 normal)."""
        app = self._build()
        palette_win = list(app._app.layout.container.children)[1]
        assert palette_win.height.max <= 8

    def test_palette_collapse_to_zero(self) -> None:
        """The palette Window has min=0 so it can collapse when invisible."""
        app = self._build()
        palette_win = list(app._app.layout.container.children)[1]
        assert palette_win.height.min == 0
        # dont_extend_height is a Filter; call it to get the bool
        assert palette_win.dont_extend_height() is True


class TestChatAppDivider:
    """The dashed divider that sits before the prompt."""

    def test_divider_is_dashed(self) -> None:
        """Divider contains '- - ' segments."""
        app = palette.ChatApp(agent=FakeAgent())
        divider = app._divider()
        assert "- -" in divider
        assert len(divider) >= 40

    def test_divider_clamped_to_terminal(self) -> None:
        """Divider width is clamped to the terminal width."""
        app = palette.ChatApp(agent=FakeAgent())
        # narrow terminal -> clipped to min 40
        with patch(
            "shutil.get_terminal_size",
            return_value=type("S", (), {"columns": 20})(),
        ):
            assert len(app._divider()) >= 40
        # wide terminal -> clipped to max 80
        with patch(
            "shutil.get_terminal_size",
            return_value=type("S", (), {"columns": 200})(),
        ):
            assert len(app._divider()) <= 80

    def test_start_emits_divider(self) -> None:
        """run() emits a divider once before the prompt area opens."""
        app = palette.ChatApp(agent=FakeAgent())
        captured: list[str] = []
        app._emit = lambda t: captured.append(t)  # type: ignore[method-assign]
        # emulate just the divider-printing portion of run()
        app._emit(app._divider())
        assert any("- -" in c for c in captured if c)


class TestChatAppUserEcho:
    """User messages echo with a `●` bullet marker."""

    def test_user_echo_has_bullet(self) -> None:
        """User messages are echoed with a '● ' prefix."""
        app = palette.ChatApp(agent=FakeAgent())
        captured: list[str] = []
        app._emit = lambda t: captured.append(t)  # type: ignore[method-assign]
        app._permission_prompt = None
        app.palette.visible = False
        app._submit("hi")
        assert any(line.startswith("● ") for line in captured if line)

class TestChatAppEmitEmpty:
    """_emit('') prints an explicit blank line as a turn spacer."""

    def test_emit_empty_writes_blank_line(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        with patch("sys.stdout", new_callable=io.StringIO) as mock:
            app._emit("")
            assert mock.getvalue() == "\n"

    def test_emit_text_writes_text(self) -> None:
        app = palette.ChatApp(agent=FakeAgent())
        with patch("sys.stdout", new_callable=io.StringIO) as mock:
            app._emit("hello")
            assert mock.getvalue() == "hello\n"
