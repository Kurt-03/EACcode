"""Tests for clarify_tool (Phase G.4, Plan G v5)."""

from __future__ import annotations

import pytest

from eaccode import clarify_tool as ct


class TestParseMultiSelect:
    def test_empty(self) -> None:
        assert ct._parse_multi_select_response("") == []

    def test_single(self) -> None:
        assert ct._parse_multi_select_response("yes") == ["yes"]

    def test_csv(self) -> None:
        assert ct._parse_multi_select_response("a, b, c") == ["a", "b", "c"]

    def test_whitespace_tolerated(self) -> None:
        assert ct._parse_multi_select_response("  a ,  b  ") == ["a", "b"]

    def test_numeric(self) -> None:
        assert ct._parse_multi_select_response("1, 3") == ["1", "3"]


class TestFlattenChoice:
    def test_string_choice(self) -> None:
        assert ct._flatten_choice("a") == "a"

    def test_structured_choice(self) -> None:
        assert ct._flatten_choice(ct.ClarifyChoice("yes", "do it")) == "yes"


class TestInvokeCallback:
    def test_no_callback_returns_none(self) -> None:
        result = ct.invoke_callback(
            None, "Q?", [ct.ClarifyChoice("a")], multi_select=False
        )
        assert result is None

    def test_callback_returns_selected(self) -> None:
        def cb(question, choices, multi_select):
            return "yes"

        result = ct.invoke_callback(
            cb, "Q?", [ct.ClarifyChoice("yes"), ct.ClarifyChoice("no")], False
        )
        assert result is not None
        assert result.selected == ["yes"]
        assert result.multi_select is False

    def test_callback_returns_multi(self) -> None:
        def cb(question, choices, multi_select):
            return "a, c"

        result = ct.invoke_callback(
            cb,
            "Q?",
            [
                ct.ClarifyChoice("a"),
                ct.ClarifyChoice("b"),
                ct.ClarifyChoice("c"),
            ],
            multi_select=True,
        )
        assert result is not None
        assert result.selected == ["a", "c"]

    def test_callback_returns_none_short_circuits(self) -> None:
        def cb(question, choices, multi_select):
            return None

        result = ct.invoke_callback(
            cb, "Q?", [ct.ClarifyChoice("yes")], multi_select=False
        )
        assert result is None


class TestRequirements:
    def test_check_returns_true(self) -> None:
        assert ct.check_clarify_requirements() is True


class TestFallbackPrompt:
    def test_renders_question_and_choices(self, monkeypatch) -> None:
        captured: list[str] = []

        def fake_print(s):
            captured.append(s)

        def fake_input(s):
            return "1"

        monkeypatch.setattr("builtins.print", fake_print)
        monkeypatch.setattr("builtins.input", fake_input)

        result = ct.fallback_cli_prompt(
            "Pick one",
            [ct.ClarifyChoice("yes", "do it"), ct.ClarifyChoice("no")],
        )
        assert result == "1"
        text = "\n".join(captured)
        assert "Pick one" in text
        assert "yes" in text
        assert "no" in text

    def test_multi_select_shows_hint(self, monkeypatch) -> None:
        captured: list[str] = []
        monkeypatch.setattr("builtins.print", lambda s: captured.append(s))
        monkeypatch.setattr("builtins.input", lambda s: "")

        ct.fallback_cli_prompt(
            "Pick many",
            [ct.ClarifyChoice("a"), ct.ClarifyChoice("b")],
            multi_select=True,
        )
        text = "\n".join(captured)
        assert "comma-separated" in text
