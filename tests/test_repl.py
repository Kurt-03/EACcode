"""Tests for the interactive shell (behavior-only REPL, Phase A7 chat)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from eaccode import __version__
from eaccode import config as cfg
from eaccode.repl import run_repl


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

    def run(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        if self.fail:
            raise RuntimeError("agent exploded")
        self.calls.append(list(messages))
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

    def test_memory_add_in_repl(self, isolated_config: Path) -> None:
        _, out = _run("/memory add wichtiger Fakt", "/memory show", "/exit")
        assert "ok" in out
        assert "wichtiger Fakt" in out
