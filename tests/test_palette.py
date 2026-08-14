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

    def test_render_has_sections_and_separator(self) -> None:
        entries = ENTRIES + [("/zeit-helfer", "skill (uhrzeit)", True)]
        prompt = palette.PalettePrompt(entries)
        prompt.refresh("/")
        lines = prompt._render_lines()
        text = "".join(part for _, part in lines)
        assert "Commands" in text
        assert "Skills" in text
        assert "─" in text  # separator
        assert "❯" in text  # marker

    def test_render_no_matches(self) -> None:
        prompt = palette.PalettePrompt(ENTRIES)
        prompt.refresh("/xyz")
        text = "".join(part for _, part in prompt._render_lines())
        assert "no matches" in text


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
            time.sleep(0.3)
            pipe.send_text("/mem")
            time.sleep(0.3)
            pipe.send_text("\r")  # enter -> picks /memory
            thread.join(timeout=5)
            assert not thread.is_alive()
            assert result.get("text") == "/memory"
