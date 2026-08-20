"""Interactive command-line shell for eaccode.

Behavior-first REPL (Phase A7): slash commands for management, plain text
goes to the agent as a chat message. The fancy UI arrives with the Textual
TUI (Phase A8).
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
from collections.abc import Iterable
from typing import Any, TextIO

from eaccode import __version__, palette, store
from eaccode.agent import Agent
from eaccode.banner import quiet as banner_quiet
from eaccode.banner import render_banner
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
    if getattr(stdout, "isatty", lambda: False)() and not banner_quiet():
        try:
            from eaccode import config as cfg

            stdout.write(render_banner(cfg.load_config()) + "\n")
            return
        except Exception:
            pass  # fall back to the compact one-liner
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


def _isatty(stream: TextIO) -> bool:
    """Check if a stream is connected to a TTY (for ANSI color decisions)."""
    try:
        return stream.isatty()
    except (AttributeError, ValueError):
        return False


def _handle_chat(
    text: str,
    agent: Agent,
    stdout: TextIO,
    chat_history: list[dict[str, Any]],
    session_id: str | None = None,
    verbose: bool = False,
) -> None:
    """Send one user message to the agent and print the final answer.

    Plan M.2: tool calls get ``⎿`` boxes, text gets a ``●`` turn marker,
    the turn ends with ``⏺ N tools used · Xs``.
    """
    import asyncio
    import time
    from eaccode.repl_render import ReplRenderer

    messages = list(chat_history) + [{"role": "user", "content": text}]
    with contextlib.suppress(Exception):
        linked = _resolve_session_links(text)
        if linked:
            messages = list(chat_history) + linked + [{"role": "user", "content": text}]

    renderer = ReplRenderer(stdout=stdout, plain=not _isatty(stdout))
    turn_start = time.monotonic()

    def on_chunk(chunk) -> None:
        renderer.on_chunk(chunk)

    try:
        history = asyncio.run(agent.run_async(messages, on_chunk=on_chunk))
    except Exception as exc:  # agent failures must not kill the REPL
        stdout.write(f"Error: {exc}\n")
        return
    # Plan M.2: emit the ⏺ N tools used · Xs summary footer
    renderer.finish(duration_s=time.monotonic() - turn_start)
    if session_id:
        with contextlib.suppress(Exception):
            # persist ONLY the new messages of this round — including tool
            # results (subagent answers etc.), so sessions are complete
            new_messages = history[len(chat_history) + 1 :]
            for message in new_messages:
                role = message.get("role")
                if role in ("user", "assistant", "tool"):
                    tool_calls = message.get("tool_calls")
                    tool_calls_str = (
                        json.dumps(tool_calls) if tool_calls else ""
                    )
                    tool_call_id = (
                        str(message.get("tool_call_id", ""))
                        if role == "tool"
                        else ""
                    )
                    store.add_message_with_tool_calls(
                        session_id,
                        role,
                        str(message.get("content", "")),
                        tool_calls=tool_calls_str,
                        tool_call_id=tool_call_id,
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
        """Permission-gate callback for run_command and other mutating tools.

        For run_command with safe-dev commands (npm/test, pytest, etc.),
        auto-allow without user prompt. For everything else, ask the user.
        """
        if name == "run_command":
            cmd = arguments.get("command", "")
            if isinstance(cmd, str):
                from eaccode.permissions import SAFE_DEV_COMMANDS_COMPILED
                for regex, desc in SAFE_DEV_COMMANDS_COMPILED:
                    if regex.search(cmd):
                        # Safe-dev command: auto-allow
                        return True
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

    On a real terminal this is the fullscreen chat REPL (Hermes style,
    input docked at the bottom); on pipes/tests the stream loop is used.

    The agent is created lazily on the first chat message, so management
    commands (/config init, ...) work even without a configured setup.
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if sys.stdin.isatty():
        try:
            from eaccode.palette import ChatApp

            ChatApp(agent=agent, agent_factory=agent_factory).run()
            stdout.write("bye\n")
            return 0
        except Exception:
            pass  # fall back to the stream loop
    return _run_stream_repl(stdin, stdout, agent, agent_factory)


def _run_stream_repl(
    stdin: TextIO,
    stdout: TextIO,
    agent: Agent | None,
    agent_factory: Any | None,
) -> int:
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
                _handle_chat(line, active, stdout, chat_history, session_id, verbose=True)
    except KeyboardInterrupt:
        stdout.write("\nbye\n")
        return 0
    stdout.write("bye\n")
    return 0
