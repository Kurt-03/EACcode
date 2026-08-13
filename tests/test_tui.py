"""Tests for the TUI skeleton (Phase A8)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from textual.widgets import Input

from eaccode import config as cfg
from eaccode.tui import EaccodeApp


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)


class FakeAgent:
    def __init__(self, reply: str = "tui antwort") -> None:
        self.reply = reply
        self.system_prompt = "system"

    def run(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        return (
            [{"role": "system", "content": self.system_prompt}]
            + list(messages)
            + [{"role": "assistant", "content": self.reply}]
        )

    def last_text(self, history: list[dict[str, Any]]) -> str:
        return self.reply


def _submit(app: EaccodeApp, text: str) -> None:
    widget = app.query_one("#input", Input)
    widget.value = text
    widget.post_message(Input.Submitted(widget, text))


async def test_app_starts_and_input_has_focus(isolated: None) -> None:
    app = EaccodeApp(agent=FakeAgent())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#input", Input).has_focus
        assert app.TITLE == "eaccode"


async def test_version_command_appears_in_log(isolated: None) -> None:
    app = EaccodeApp(agent=FakeAgent())
    async with app.run_test() as pilot:
        await pilot.pause()
        _submit(app, "/version")
        await pilot.pause()
        assert "eaccode 0.0.1" in app._log_text


async def test_unknown_slash_does_not_crash(isolated: None) -> None:
    app = EaccodeApp(agent=FakeAgent())
    async with app.run_test() as pilot:
        await pilot.pause()
        _submit(app, "/nonsense")
        await pilot.pause()
        assert "Unknown command" in app._log_text


async def test_clear_resets_log(isolated: None) -> None:
    app = EaccodeApp(agent=FakeAgent())
    async with app.run_test() as pilot:
        await pilot.pause()
        _submit(app, "/version")
        await pilot.pause()
        _submit(app, "/clear")
        await pilot.pause()
        assert app._log_text == ""


async def test_chat_message_roundtrip(isolated: None) -> None:
    app = EaccodeApp(agent=FakeAgent(reply="hallo aus der TUI"))
    async with app.run_test() as pilot:
        await pilot.pause()
        _submit(app, "hallo")
        await pilot.pause()
        await pilot.pause()
        assert "> hallo" in app._log_text
        assert "hallo aus der TUI" in app._log_text
