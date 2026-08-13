"""Command-line entry point for eaccode."""

from __future__ import annotations

import argparse
from typing import TextIO

from eaccode import __version__
from eaccode.repl import run_repl

DESCRIPTION = (
    "Self-improving generalist agent - Hermes-inspired orchestration "
    "with Claude-Code-level coding."
)


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (kept separate for testability)."""
    parser = argparse.ArgumentParser(
        prog="eaccode",
        description=DESCRIPTION,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"eaccode {__version__}",
    )
    return parser


def main(
    argv: list[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Entry point: flags like --version, otherwise start the interactive shell."""
    build_parser().parse_args(argv)
    raise SystemExit(run_repl(stdin, stdout))
