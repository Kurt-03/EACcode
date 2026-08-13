"""Interactive command-line shell for eaccode.

Behavior-first REPL (Phase A7): slash commands for management, plain text
goes to the agent as a chat message. The fancy UI arrives with the Textual
TUI (Phase A8).
"""

from __future__ import annotations

import sys
from typing import Any, TextIO

from eaccode import __version__
from eaccode.agent import Agent
from eaccode.commands import (
    run_config_command,
    run_memory_command,
    run_model_command,
    run_provider_command,
)
from eaccode.memory import injection_text

HELP_TEXT = """\
Commands:
  /help           show this help
  /version        show eaccode version
  /clear          clear the screen and the chat history
  /config <cmd>   manage configuration (init, show, set, ...)
  /provider <cmd> manage providers (add, list, remove, set-key)
  /model <cmd>    manage models (list, set-default, ping, ...)
  /memory <cmd>   manage memory (add, show, remove, user add)
  /exit           leave eaccode (alias: /quit)

Everything else is sent to the agent as a chat message.
"""


def _print_banner(stdout: TextIO) -> None:
    stdout.write(
        f"eaccode {__version__} - self-improving generalist agent. "
        "Type /help for commands.\n"
    )


def _clear_screen(stdout: TextIO) -> None:
    if getattr(stdout, "isatty", lambda: False)():
        stdout.write("\x1b[2J\x1b[H")


def _handle_command(
    command: str, stdout: TextIO, stdin: TextIO, chat_history: list[dict[str, Any]]
) -> int | None:
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
        chat_history.clear()
    elif name == "config":
        run_config_command(command.split()[1:], stdout=stdout, stdin=stdin)
    elif name == "provider":
        run_provider_command(command.split()[1:], stdout=stdout)
    elif name == "model":
        run_model_command(command.split()[1:], stdout=stdout)
    elif name == "memory":
        run_memory_command(command.split()[1:], stdout=stdout)
    else:
        stdout.write(f"Unknown command: /{name} - type /help for a list of commands.\n")
    return None


def _handle_chat(
    text: str,
    agent: Agent,
    stdout: TextIO,
    chat_history: list[dict[str, Any]],
) -> None:
    """Send one user message to the agent and print the final answer."""
    messages = list(chat_history) + [{"role": "user", "content": text}]
    try:
        history = agent.run(messages)
    except Exception as exc:  # agent failures must not kill the REPL
        stdout.write(f"Error: {exc}\n")
        return
    answer = agent.last_text(history)
    stdout.write(f"eaccode> {answer}\n")
    chat_history[:] = history[1:]  # keep the conversation (drop the system message)


def _wire_permission_prompt(stdin: TextIO, stdout: TextIO) -> None:
    """Ask y/N on stdout when the agent wants to run a shell command."""

    def ask(command: str) -> bool:
        stdout.write(f"Allow: {command} [y/N] ")
        stdout.flush()
        try:
            answer = stdin.readline()
        except Exception:
            return False
        return answer.strip().lower() in ("y", "yes")

    from eaccode import tools

    tools.permission_handler = ask


def run_repl(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    agent: Agent | None = None,
    agent_factory: Any | None = None,
) -> int:
    """Run the interactive shell until /exit, Ctrl+C or EOF. Returns exit code.

    The agent is created lazily on the first chat message, so management
    commands (/config init, ...) work even without a configured setup.
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    active_agent = agent
    chat_history: list[dict[str, Any]] = []
    _print_banner(stdout)

    def get_agent() -> Agent:
        nonlocal active_agent
        if active_agent is None:
            active_agent = agent_factory() if agent_factory else Agent()
            # Prepend learned memory to the system prompt of the shared agent.
            memory_block = injection_text()
            if memory_block:
                active_agent.system_prompt = f"{active_agent.system_prompt}\n\n{memory_block}"
        return active_agent

    _wire_permission_prompt(stdin, stdout)
    try:
        for raw_line in stdin:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("/"):
                code = _handle_command(line[1:], stdout, stdin, chat_history)
                if code is not None:
                    stdout.write("bye\n")
                    return code
            else:
                try:
                    active = get_agent()
                except Exception as exc:
                    stdout.write(f"Error: {exc}\n")
                    continue
                _handle_chat(line, active, stdout, chat_history)
    except KeyboardInterrupt:
        stdout.write("\nbye\n")
        return 0
    stdout.write("bye\n")
    return 0
