"""Tests for the slash palette (variante A)."""

from __future__ import annotations

from typing import Any

import pytest

from eaccode import palette


class TestFuzzy:
    def test_subsequence_match(self) -> None:
        assert palette.fuzzy_match("mcp", "mcp")
        assert palette.fuzzy_match("mem", "memory")
        assert palette.fuzzy_match("mry", "memory")  # subsequence
        assert palette.fuzzy_match("", "anything")
        assert not palette.fuzzy_match("xyz", "memory")
        assert palette.fuzzy_match("MEM", "memory")  # case-insensitive

    def test_skill_matches_trigger(self) -> None:
        assert palette.fuzzy_match("uhr", "uhrzeit")


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
        assert skills_entry[2] is True  # flagged as skill

    def test_skills_failure_is_silent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from eaccode import skills

        def broken() -> list[Any]:
            raise OSError("no skills dir")

        monkeypatch.setattr(skills, "list_skills", broken)
        entries = palette.palette_entries()
        assert any(entry[0] == "/help" for entry in entries)


class TestCompleter:
    def test_completes_for_slash_word(self) -> None:
        entries = [
            ("/memory", "memory verwalten", False),
            ("/model", "modelle", False),
            ("/mcp", "mcp server", False),
            ("/zeit-helfer", "skill (uhrzeit)", True),
        ]
        completer = palette._SlashCompleter(entries)

        class Doc:
            def get_word_before_cursor(self) -> str:
                return "/m"

        completions = list(completer.get_completions(Doc(), None))
        texts = {completion.text for completion in completions}
        assert texts == {"/memory", "/model", "/mcp"}

    def test_no_completions_without_slash(self) -> None:
        completer = palette._SlashCompleter([("/help", "x", False)])

        class Doc:
            def get_word_before_cursor(self) -> str:
                return "hello"

        assert list(completer.get_completions(Doc(), None)) == []

    def test_skill_has_meta(self) -> None:
        completer = palette._SlashCompleter([("/zeit-helfer", "skill (uhrzeit)", True)])

        class Doc:
            def get_word_before_cursor(self) -> str:
                return "/z"

        completions = list(completer.get_completions(Doc(), None))
        assert "skill" in str(completions[0].display_meta)
