"""Tests for the interactive shell (behavior-only REPL)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from eaccode import __version__
from eaccode import config as cfg
from eaccode.repl import run_repl


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the config layer at a temp location so tests are deterministic."""
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(cfg, "config_path", lambda: target)
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    return target


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


def test_plain_text_hints_chat_comes_later() -> None:
    _, out = _run("hallo", "/exit")
    assert "Phase A7" in out


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
