"""Tests for plan mode (Plan I P1.6)."""

from __future__ import annotations

import pytest

from eaccode import plan_mode as pm


class TestExtractPlan:
    def test_simple(self) -> None:
        text = "I will refactor X. <plan>1. Edit foo.py\n2. Run tests</plan> Done."
        assert pm.extract_plan_from_text(text) == "1. Edit foo.py\n2. Run tests"

    def test_multiline(self) -> None:
        text = """Sure thing.

        <plan>
        1. Read foo.py
        2. Patch the bug
        3. Run pytest
        </plan>

        That's the plan.
        """
        result = pm.extract_plan_from_text(text)
        assert result is not None
        assert "Read foo.py" in result
        assert "Run pytest" in result

    def test_no_plan(self) -> None:
        assert pm.extract_plan_from_text("I will just do it") is None

    def test_case_insensitive(self) -> None:
        text = "<PLAN>refactor foo</PLAN>"
        assert pm.extract_plan_from_text(text) == "refactor foo"


class TestReadOnlyTools:
    def test_read_only_includes_read(self) -> None:
        assert pm.is_read_only_tool("read_file") is True

    def test_read_only_includes_list(self) -> None:
        assert pm.is_read_only_tool("list_files") is True

    def test_write_blocked(self) -> None:
        assert pm.is_plan_blocked_tool("write_file") is True

    def test_run_command_blocked(self) -> None:
        assert pm.is_plan_blocked_tool("run_command") is True

    def test_unknown_blocked(self) -> None:
        assert pm.is_plan_blocked_tool("totally-unknown-tool") is True

    def test_explanation(self) -> None:
        msg = pm.explain_plan_block("write_file")
        assert "write_file" in msg
        assert "plan" in msg.lower()