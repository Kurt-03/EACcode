"""Command-line entry point for eaccode."""

from __future__ import annotations

import sys
from typing import TextIO

from eaccode import __version__
from eaccode.commands import (
    run_config_command,
    run_model_command,
    run_provider_command,
)
from eaccode.config import load_env
from eaccode.repl import run_repl

DESCRIPTION = (
    "Self-improving generalist agent - Hermes-inspired orchestration "
    "with Claude-Code-level coding."
)


def main(
    argv: list[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Entry point: flags, config subcommands, or the interactive shell."""
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    load_env()
    if not argv:
        raise SystemExit(run_repl(stdin, stdout))
    first = argv[0]
    if first in ("--version", "-V"):
        stdout.write(f"eaccode {__version__}\n")
        raise SystemExit(0)
    if first in ("--help", "-h"):
        stdout.write(f"{DESCRIPTION}\n\nUsage: eaccode [--version] [config <command>]\n")
        raise SystemExit(0)
    if first == "config":
        raise SystemExit(run_config_command(argv[1:], stdout=stdout, stdin=stdin))
    if first == "provider":
        raise SystemExit(run_provider_command(argv[1:], stdout=stdout))
    if first == "model":
        raise SystemExit(run_model_command(argv[1:], stdout=stdout))
    stdout.write(f"Unknown command: {first} - try 'eaccode --help'\n")
    raise SystemExit(2)
