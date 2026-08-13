"""Interactive command-line shell for eaccode.

Behavior-only REPL — the fancy UI arrives with the Textual TUI (Phase A8).
"""

from __future__ import annotations

import sys
from typing import TextIO

from eaccode import __version__

HELP_TEXT = """\
Commands:
  /help       show this help
  /version    show eaccode version
  /clear      clear the screen
  /exit       leave eaccode (alias: /quit)

Chat mode arrives in Phase A7 - for now this shell only runs commands.
"""


def _print_banner(stdout: TextIO) -> None:
    stdout.write(
        f"eaccode {__version__} - self-improving generalist agent. "
        "Type /help for commands.\n"
    )


def _clear_screen(stdout: TextIO) -> None:
    if getattr(stdout, "isatty", lambda: False)():
        stdout.write("\x1b[2J\x1b[H")


def _handle_command(command: str, stdout: TextIO) -> int | None:
    """Dispatch one slash-command; return an exit code or None to continue."""
    name = command.split()[0] if command else ""
    if name in ("exit", "quit"):
        return 0
    if name == "help":
        stdout.write(HELP_TEXT)
    elif name == "version":
        stdout.write(f"eaccode {__version__}\n")
    elif name == "clear":
        _clear_screen(stdout)
    else:
        stdout.write(f"Unknown command: /{name} - type /help for a list of commands.\n")
    return None


def run_repl(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    """Run the interactive shell until /exit, Ctrl+C or EOF. Returns exit code."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    _print_banner(stdout)
    try:
        for raw_line in stdin:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("/"):
                code = _handle_command(line[1:], stdout)
                if code is not None:
                    stdout.write("bye\n")
                    return code
            else:
                stdout.write(
                    "Chat is not implemented yet (Phase A7) - type /help for commands.\n"
                )
    except KeyboardInterrupt:
        stdout.write("\nbye\n")
        return 0
    stdout.write("bye\n")
    return 0
