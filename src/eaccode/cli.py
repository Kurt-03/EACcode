"""Command-line entry point for eaccode."""

from __future__ import annotations

import argparse

from eaccode import __version__

DESCRIPTION = (
    "Self-improving generalist agent — Hermes-inspired orchestration "
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


def main(argv: list[str] | None = None) -> None:
    """Entry point: parse arguments and dispatch (chat loop arrives in Phase A7)."""
    build_parser().parse_args(argv)
