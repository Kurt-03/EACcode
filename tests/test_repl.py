"""Tests for the interactive shell (behavior-only REPL, Phase A7 chat)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from eaccode import __version__, repl, store
from eaccode import config as cfg
from eaccode.repl import run_repl


@pytest.fixture(autouse=True)
def _isolated_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every REPL test gets a temp data dir (no real DB writes)."""
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the config + data layer at a temp location for determinism."""
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(cfg, "config_path", lambda: target)
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    return target


class FakeAgent:
    """Minimal agent double: records messages, returns a canned answer."""

    def __init__(self, reply: str = "fake answer", fail: bool = False) -> None:
        self.reply = reply
        self.fail = fail
        self.calls: list[list[dict[str, str]]] = []
        self.system_prompt = "system"

    def run(self, messages: list[dict[str, str]], **kwargs: Any) -> list[dict[str, Any]]:
        """Accept Plan-K kwargs (on_chunk, on_token, session_key, etc.).

        When on_chunk is provided, we feed it a synthetic text + done
        chunk so renderers that listen for streaming still get data.
        """
        if self.fail:
            raise RuntimeError("agent exploded")
        self.calls.append(list(messages))
        on_chunk = kwargs.get("on_chunk")
        if on_chunk is not None:
            from eaccode.providers.base import StreamChunk
            on_chunk(StreamChunk(kind="text", content=self.reply))
            on_chunk(StreamChunk(kind="done", stop_reason="end_turn"))
        return (
            [{"role": "system", "content": self.system_prompt}]
            + list(messages)
            + [{"role": "assistant", "content": self.reply}]
        )

    def last_text(self, history: list[dict[str, Any]]) -> str:
        return self.reply


def _run(*lines: str) -> tuple[int, str]:
    stdin = io.StringIO("\n".join(lines) + "\n")
    stdout = io.StringIO()
    code = run_repl(stdin, stdout)
    return code, stdout.getvalue()


def test_banner_shows_name_and_version() -> None:
    code, out = _run("/exit")
    assert code == 0
    assert f"eaccode {__version__}" in out


def test_version_command_prints_version() -> None:
    _, out = _run("/version", "/exit")
    assert f"eaccode {__version__}" in out


def test_help_lists_commands() -> None:
    _, out = _run("/help", "/exit")
    for cmd in ("/help", "/version", "/clear", "/exit"):
        assert cmd in out


def test_exit_command_ends_session() -> None:
    code, out = _run("/exit")
    assert code == 0
    assert "bye" in out


def test_quit_alias_ends_session() -> None:
    code, _ = _run("/quit")
    assert code == 0


def test_unknown_command_prints_hint() -> None:
    _, out = _run("/foo", "/exit")
    assert "Unknown command" in out
    assert "/help" in out


def test_plain_text_without_agent_reports_clean_error(isolated_config: Path) -> None:
    """Chatting without a configured setup must not crash the REPL."""
    code, out = _run("hallo", "/exit")
    assert code == 0
    assert "Error" in out
    assert "bye" in out


def test_empty_lines_are_ignored() -> None:
    code, _ = _run("", "  ", "/exit")
    assert code == 0


def test_eof_ends_session_cleanly() -> None:
    stdout = io.StringIO()
    assert run_repl(io.StringIO(""), stdout) == 0
    assert "bye" in stdout.getvalue()


def test_keyboard_interrupt_ends_cleanly() -> None:
    class InterruptingInput:
        def __iter__(self) -> object:
            raise KeyboardInterrupt

    stdout = io.StringIO()
    assert run_repl(InterruptingInput(), stdout) == 0
    assert "bye" in stdout.getvalue()


def test_clear_does_not_crash_without_tty() -> None:
    code, _ = _run("/clear", "/exit")
    assert code == 0


def test_config_command_runs_in_repl(isolated_config: Path) -> None:
    _, out = _run("/config path", "/exit")
    assert "config.yaml" in out


def test_config_error_does_not_kill_repl(isolated_config: Path) -> None:
    code, out = _run("/config show", "/exit")
    assert code == 0
    assert "Error" in out
    assert "bye" in out


class TestParseArgs:
    def test_simple_split(self) -> None:
        assert repl.parse_args("memory add wichtiger Fakt") == [
            "memory",
            "add",
            "wichtiger",
            "Fakt",
        ]

    def test_double_quotes_group(self) -> None:
        assert repl.parse_args('skill new x --description "mehrere Worte hier"') == [
            "skill",
            "new",
            "x",
            "--description",
            "mehrere Worte hier",
        ]

    def test_single_quotes_group(self) -> None:
        assert repl.parse_args("memory add 'ein Fakt'") == ["memory", "add", "ein Fakt"]

    def test_windows_path_keeps_backslashes(self) -> None:
        assert repl.parse_args('config show "C:\\Users\\kurtj"') == [
            "config",
            "show",
            "C:\\Users\\kurtj",
        ]

    def test_unterminated_quote_raises(self) -> None:
        with pytest.raises(ValueError):
            repl.parse_args('memory add "kaputt')

    def test_empty_and_whitespace(self) -> None:
        assert repl.parse_args("") == []
        assert repl.parse_args("   ") == []


class TestChat:
    def test_plain_text_goes_to_agent(self, isolated_config: Path) -> None:
        agent = FakeAgent(reply="hallo zurück")
        stdin = io.StringIO("hallo\n/exit\n")
        stdout = io.StringIO()
        assert run_repl(stdin, stdout, agent=agent) == 0
        assert "eaccode> hallo zurück" in stdout.getvalue()
        assert agent.calls[0][-1] == {"role": "user", "content": "hallo"}

    def test_conversation_history_kept(self, isolated_config: Path) -> None:
        agent = FakeAgent()
        run_repl(io.StringIO("erste\nzweite\n/exit\n"), io.StringIO(), agent=agent)
        second_call = agent.calls[1]
        roles = [m["role"] for m in second_call]
        assert roles[-3:] == ["user", "assistant", "user"]
        assert second_call[-1]["content"] == "zweite"

    def test_clear_resets_history(self, isolated_config: Path) -> None:
        agent = FakeAgent()
        run_repl(io.StringIO("erste\n/clear\nzweite\n/exit\n"), io.StringIO(), agent=agent)
        assert len(agent.calls) == 2
        assert agent.calls[1][-1]["content"] == "zweite"
        assert agent.calls[1][0]["role"] == "user"  # no leftover history

    def test_agent_failure_keeps_repl_alive(self, isolated_config: Path) -> None:
        agent = FakeAgent(fail=True)
        stdout = io.StringIO()
        code = run_repl(io.StringIO("hallo\n/exit\n"), stdout, agent=agent)
        assert code == 0
        assert "Error: agent exploded" in stdout.getvalue()
        assert "bye" in stdout.getvalue()

    def test_memory_show_in_repl(self, isolated_config: Path) -> None:
        _, out = _run("/memory show", "/exit")
        assert "(memory is empty)" in out

    def test_unterminated_quote_reports_error(
        self, isolated_config: Path
    ) -> None:
        _, out = _run('/memory add "kaputt', "/exit")
        assert "unterminated quote" in out

    def test_memory_add_with_quoted_text(self, isolated_config: Path) -> None:
        _, out = _run('/memory add "wichtiger Fakt"', "/memory show", "/exit")
        assert "ok" in out
        assert "wichtiger Fakt" in out

    def test_job_command_in_repl(self, isolated_config: Path) -> None:
        _, out = _run("/job list", "/exit")
        assert "no jobs yet" in out

    def test_mcp_command_in_repl(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cfg, "config_dir", lambda: isolated_config)
        cfg.ensure_config()
        _, out = _run("/mcp list", "/exit")
        assert "no servers yet" in out

    def test_memory_add_in_repl(self, isolated_config: Path) -> None:
        _, out = _run("/memory add wichtiger Fakt", "/memory show", "/exit")
        assert "ok" in out
        assert "wichtiger Fakt" in out

    def test_chat_persisted_to_store(self, isolated_config: Path) -> None:
        agent = FakeAgent(reply="hallo zurück")
        code = run_repl(
            io.StringIO("hallo welt\n/exit\n"), io.StringIO(), agent=agent
        )
        assert code == 0
        sessions = store.browse()
        assert len(sessions) == 1
        assert sessions[0].title == "hallo welt"
        messages = store.show(sessions[0].id)
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "hallo welt"

    def test_tool_messages_persisted(self, isolated_config: Path) -> None:
        class ToolAgent(FakeAgent):
            def run(self, messages: list[dict[str, str]], **kwargs: Any) -> list[dict[str, Any]]:
                return [{"role": "system", "content": "s"}] + messages + [
                    {"role": "assistant", "content": ""},
                    {"role": "tool", "content": "subagent-ergbnis: 42"},
                    {"role": "assistant", "content": "finale antwort"},
                ]

        code = run_repl(
            io.StringIO("starte subagenten\n/exit\n"),
            io.StringIO(),
            agent=ToolAgent(),
        )
        assert code == 0
        roles = [m["role"] for m in store.show(store.browse()[0].id)]
        assert roles == ["user", "assistant", "tool", "assistant"]
        assert "subagent-ergbnis: 42" in store.show(store.browse()[0].id)[2]["content"]

    def test_session_command_in_repl(self, isolated_config: Path) -> None:
        agent = FakeAgent(reply="antwort")
        run_repl(io.StringIO("wichtige frage\n/exit\n"), io.StringIO(), agent=agent)
        _, out = _run("/session browse", "/session search wichtige", "/exit")
        assert "wichtige frage" in out
        assert "2 msgs" in out

    def test_session_link_injects_context(self, isolated_config: Path) -> None:
        agent = FakeAgent(reply="antwort")
        run_repl(io.StringIO("erste frage\n/exit\n"), io.StringIO(), agent=agent)
        session_id = store.browse()[0].id
        agent2 = FakeAgent(reply="ok")
        run_repl(
            io.StringIO(f"was war da? @session:{session_id}\n/exit\n"),
            io.StringIO(),
            agent=agent2,
        )
        last_call = agent2.calls[-1]
        roles = [m["role"] for m in last_call]
        assert roles == ["system", "user"]  # linked context + user question
        context = last_call[0]["content"]
        assert "Referenced session" in context
        assert "erste frage" in context
