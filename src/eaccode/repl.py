"""Interactive command-line shell for eaccode.

Behavior-first REPL (Phase A7): slash commands for management, plain text
goes to the agent as a chat message. The fancy UI arrives with the Textual
TUI (Phase A8).
"""

from __future__ import annotations

import contextlib
import re
import sys
from collections.abc import Iterable
from typing import Any, TextIO

from eaccode import __version__, palette, store
from eaccode.agent import Agent
from eaccode.commands import (
    HELP_TEXT,
    parse_args,
    run_config_command,
    run_job_command,
    run_mcp_command,
    run_memory_command,
    run_model_command,
    run_permissions_command,
    run_provider_command,
    run_session_command,
    run_skill_command,
)
from eaccode.memory import injection_text


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
    try:
        parts = parse_args(command)
    except ValueError as exc:
        stdout.write(f"Error: {exc}\n")
        return None
    name = parts[0] if parts else ""
    rest = parts[1:]
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
        run_config_command(rest, stdout=stdout, stdin=stdin)
    elif name == "provider":
        run_provider_command(rest, stdout=stdout)
    elif name == "model":
        run_model_command(rest, stdout=stdout)
    elif name == "memory":
        run_memory_command(rest, stdout=stdout)
    elif name == "skill":
        run_skill_command(rest, stdout=stdout)
    elif name == "session":
        run_session_command(rest, stdout=stdout)
    elif name == "permissions":
        run_permissions_command(rest, stdout=stdout)
    elif name == "job":
        run_job_command(rest, stdout=stdout)
    elif name == "mcp":
        run_mcp_command(rest, stdout=stdout)
    else:
        stdout.write(f"Unknown command: /{name} - type /help for a list of commands.\n")
    return None


SESSION_LINK_RE = re.compile(r"@session:([A-Za-z0-9_]+)")


def _resolve_session_links(text: str) -> list[dict[str, Any]]:
    """Resolve @session:<id> references into system context messages."""
    context: list[dict[str, Any]] = []
    for match in SESSION_LINK_RE.finditer(text):
        session_id = match.group(1)
        messages = store.show(session_id)
        if not messages:
            continue
        rendered = "\n".join(f"[{m['role']}] {m['content']}" for m in messages)
        context.append(
            {
                "role": "system",
                "content": (
                    f"## Referenced session {session_id} (context for the user's "
                    f"question):\n{rendered}"
                ),
            }
        )
    return context


def _handle_chat(
    text: str,
    agent: Agent,
    stdout: TextIO,
    chat_history: list[dict[str, Any]],
    session_id: str | None = None,
) -> None:
    """Send one user message to the agent and print the final answer."""
    messages = list(chat_history) + [{"role": "user", "content": text}]
    with contextlib.suppress(Exception):
        linked = _resolve_session_links(text)
        if linked:
            messages = list(chat_history) + linked + [{"role": "user", "content": text}]
    try:
        history = agent.run(messages)
    except Exception as exc:  # agent failures must not kill the REPL
        stdout.write(f"Error: {exc}\n")
        return
    answer = agent.last_text(history)
    stdout.write(f"eaccode> {answer}\n")
    if session_id:
        with contextlib.suppress(Exception):
            # persist ONLY the new messages of this round — including tool
            # results (subagent answers etc.), so sessions are complete
            new_messages = history[len(chat_history) + 1 :]
            for message in new_messages:
                role = message.get("role")
                if role in ("user", "assistant", "tool"):
                    store.add_message(
                        session_id, role, str(message.get("content", ""))
                    )
    chat_history[:] = history[1:]  # keep the conversation (drop the system message)


def _wire_permission_prompt(
    stdin: TextIO, stdout: TextIO, manager: Any | None = None
) -> None:
    """Ask y/N on stdout when the agent wants to run a tool or command."""

    def ask(command: str) -> bool:
        stdout.write(f"Allow: {command} [y/N] ")
        stdout.flush()
        try:
            answer = stdin.readline()
        except Exception:
            return False
        return answer.strip().lower() in ("y", "yes")

    def ask_tool(name: str, arguments: dict[str, Any]) -> bool:
        return ask(f"{name} {arguments}")

    from eaccode import tools

    tools.permission_handler = ask
    if manager is not None:
        manager.ask_handler = ask_tool


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
    session_id: str | None = None
    _print_banner(stdout)
    with contextlib.suppress(Exception):
        session_id = store.new_session(platform="cli")  # store unavailable -> None

    def get_agent() -> Agent:
        nonlocal active_agent
        if active_agent is None:
            active_agent = agent_factory() if agent_factory else Agent()
            # Prepend learned memory to the system prompt of the shared agent.
            memory_block = injection_text()
            if memory_block:
                active_agent.system_prompt = f"{active_agent.system_prompt}\n\n{memory_block}"
            # C1: wire the interactive ask prompt into the permission manager
            manager = getattr(active_agent, "permission_manager", None)
            if manager is not None:
                _wire_permission_prompt(stdin, stdout, manager)
        return active_agent

    _wire_permission_prompt(stdin, stdout)

    def _input_lines() -> Iterable[str]:
        """Interactive TTY: slash palette; otherwise plain stdin lines."""
        if sys.stdin.isatty():
            while True:
                try:
                    yield palette.repl_prompt()
                except (EOFError, KeyboardInterrupt):
                    return
        else:
            yield from stdin

    try:
        for raw_line in _input_lines():
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
                if session_id and not chat_history:
                    with contextlib.suppress(Exception):
                        store.set_title(session_id, line)
                _handle_chat(line, active, stdout, chat_history, session_id)
    except KeyboardInterrupt:
        stdout.write("\nbye\n")
        return 0
    stdout.write("bye\n")
    return 0
