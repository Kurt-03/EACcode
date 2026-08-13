"""Tests for the eaccode CLI entry point (Phase A1 scaffold)."""

from __future__ import annotations

import io

import pytest

from eaccode import __version__
from eaccode.cli import main


def test_version_flag_prints_name_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    """`eaccode --version` must print `eaccode <version>` and exit 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == f"eaccode {__version__}"


def test_help_flag_describes_agent(capsys: pytest.CaptureFixture[str]) -> None:
    """`eaccode --help` must describe the product and exit 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "agent" in captured.out.lower()


def test_bare_invocation_starts_shell() -> None:
    """Bare `eaccode` must start the interactive shell and exit cleanly on EOF."""
    with pytest.raises(SystemExit) as exc_info:
        main([], stdin=io.StringIO(""), stdout=io.StringIO())
    assert exc_info.value.code == 0
