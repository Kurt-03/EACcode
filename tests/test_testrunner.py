"""Tests for the test runner (Phase D3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import testrunner
from eaccode.testrunner import format_report, parse_failures


@pytest.fixture
def green_repo(tmp_path: Path) -> Path:
    (tmp_path / "test_ok.py").write_text(
        "def test_one():\n    assert 1 == 1\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def red_repo(tmp_path: Path) -> Path:
    (tmp_path / "test_bad.py").write_text(
        "def test_fails():\n    assert 1 == 2\n", encoding="utf-8"
    )
    return tmp_path


class TestRunTests:
    def test_green_suite(self, green_repo: Path) -> None:
        report = testrunner.run_tests(str(green_repo))
        assert "OK (exit 0)" in report
        assert "passed 1" in report

    def test_red_suite_lists_failures(self, red_repo: Path) -> None:
        report = testrunner.run_tests(str(red_repo))
        assert "FAIL (exit 1)" in report
        assert "test_bad.py::test_fails" in report

    def test_missing_dir(self, tmp_path: Path) -> None:
        report = testrunner.run_tests(str(tmp_path / "ghost"))
        assert "Error" in report

    def test_single_test_file(self, green_repo: Path) -> None:
        report = testrunner.run_tests(str(green_repo), test_file="test_ok.py")
        assert "passed 1" in report


class TestParsing:
    def test_parse_failures(self) -> None:
        output = (
            "FAILED tests/test_a.py::test_x - assert 1\n"
            "FAILED tests/test_b.py::test_y\n"
            "ERROR tests/test_c.py::test_z\n"
        )
        assert parse_failures(output) == [
            "tests/test_a.py::test_x",
            "tests/test_b.py::test_y",
            "tests/test_c.py::test_z",
        ]

    def test_format_report_ok(self) -> None:
        report = format_report("1 passed in 0.1s", 0)
        assert "OK (exit 0)" in report
        assert "passed 1" in report

    def test_format_report_fail(self) -> None:
        output = "FAILED tests/test_bad.py::test_fails - assert 1 == 2\n1 failed in 0.1s"
        report = format_report(output, 1)
        assert "FAIL (exit 1)" in report
        assert "tests/test_bad.py::test_fails" in report


class TestTools:
    def test_make_test_tools(self) -> None:
        tools = {tool.name: tool for tool in testrunner.make_test_tools()}
        assert set(tools) == {"run_tests"}

    def test_tool_runs_suite(self, green_repo: Path) -> None:
        tool = testrunner.make_test_tools()[0]
        out = tool.func(str(green_repo))
        assert "OK" in out
