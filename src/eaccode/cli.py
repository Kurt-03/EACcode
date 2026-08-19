"""Command-line entry point for eaccode."""

from __future__ import annotations

import sys
from typing import TextIO

from eaccode import __version__
from eaccode import config as cfg
from eaccode.agent import DEFAULT_SYSTEM_PROMPT, Agent
from eaccode.browser import make_browser_tools
from eaccode.commands import (
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
from eaccode.config import load_env
from eaccode.editing import make_editing_tools
from eaccode.git import make_git_tools
from eaccode.learning import LEARNING_PROMPT, make_learning_tools
from eaccode.memory import injection_text, make_memory_tools
from eaccode.permissions import PermissionManager
from eaccode.permissions import mode_hint as permissions_mode_hint
from eaccode.repl import run_repl
from eaccode.repo import make_repo_tools
from eaccode.store import make_session_tools
from eaccode.subagents import SubagentPool, make_subagent_tool
from eaccode.testrunner import make_test_tools
from eaccode.tools import BUILTIN_TOOLS

DESCRIPTION = (
    "Self-improving generalist agent - Hermes-inspired orchestration "
    "with Claude-Code-level coding."
)


def build_agent(
    conf=None,
    max_turns: int | None = None,
    max_output_tokens: int | None = None,
) -> Agent:
    """Build the agent with built-in tools, learning loop and memory injection."""
    system_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n\n{LEARNING_PROMPT}"
    memory_block = injection_text()
    if memory_block:
        system_prompt = f"{system_prompt}\n\n{memory_block}"
    tools = (
        list(BUILTIN_TOOLS)
        + make_learning_tools()
        + make_session_tools()
        + make_memory_tools()
        + make_repo_tools()
        + make_editing_tools()
        + make_test_tools()
        + make_git_tools()
        + make_browser_tools()
    )
    registry = {tool.name: tool for tool in tools}
    pool = SubagentPool()
    tools.append(make_subagent_tool(pool, registry, cfg.load_config()))
    # C3: MCP servers from config -> discovered tools (mcp__<server>__<tool>)
    from eaccode.mcp import build_mcp_clients, make_mcp_tools

    mcp_clients = build_mcp_clients()
    if mcp_clients:
        tools.extend(make_mcp_tools(mcp_clients))
    # C1: tell the agent its permission mode up front
    permission_manager = PermissionManager()
    # Smart mode: register the aux LLM reviewer
    if permission_manager.mode == "smart":
        from eaccode.smart_approval import SmartApprovalReviewer

        conf = cfg.load_config()
        model_id = conf.get("model", {}).get("default") or ""
        provider_name, _, _ = model_id.partition("/")
        provider_config = (conf.get("providers") or {}).get(provider_name, {})
        if model_id and provider_config:
            from eaccode.providers import registry as provider_registry

            try:
                provider = provider_registry.get(
                    provider_name, provider_config, model=model_id
                )
                permission_manager.smart_reviewer = SmartApprovalReviewer(
                    provider, timeout=10.0
                ).review
            except Exception as exc:
                # Fall back to ask mode if provider registration fails
                print(f"Warning: smart review setup failed: {exc}")

    system_prompt = f"{system_prompt}{permissions_mode_hint(permission_manager.mode)}"
    if conf is None:
        conf = cfg.load_config()
    return Agent(
        tools=tools,
        system_prompt=system_prompt,
        permission_manager=permission_manager,
        conf=conf,
        max_turns=max_turns,
        max_output_tokens=max_output_tokens,
    )


def _run_once(
    prompt: str,
    stdout: TextIO,
    max_turns: int | None = None,
    max_output_tokens: int | None = None,
    verbose: bool = False,
) -> int:
    """Non-interactive mode: one user message, print the answer.

    With ``verbose=True`` (via ``--verbose``), tool calls and tool
    results are printed inline as they happen (Plan K K.3).
    """
    from eaccode.render import render_chunk

    agent = build_agent()
    # Wire tools.permission_handler to the agent's PermissionManager so
    # run_command's secondary check passes for safe-dev commands.
    # (repl.py does the same at startup.)
    from eaccode import tools
    pm = agent.permission_manager
    def ask(cmd: str) -> bool:
        d = pm.check("run_command", {"command": cmd})
        return d.allow

    tools.set_loop_permission_checked(False)
    tools.permission_handler = ask
    chunks: list = []

    def on_chunk(chunk) -> None:
        chunks.append(chunk)
        if not verbose:
            return
        if chunk.kind == "text" and chunk.content:
            # Plan M: split text-chunks internally so user perceives streaming.
            # Real providers (especially MiniMax) often send the whole answer
            # as one chunk. We re-emit that text in smaller sub-chunks with
            # a delay so the user actually sees the text appear.
            from eaccode.agent import _split_for_pseudo_stream
            import time as _t
            for piece in _split_for_pseudo_stream(chunk.content, chunk_size=12):
                stdout.write(piece)
                stdout.flush()
                _t.sleep(0.06)
            return
        if chunk.kind == "done":
            return
        rendered = render_chunk(chunk, verbose=True)
        if rendered:
            stdout.write(rendered)
            stdout.flush()

    try:
        from eaccode.agent import MAX_TURNS, MAX_OUTPUT_TOKENS, _pseudo_stream_text
        history = agent.run(
            [{"role": "user", "content": prompt}],
            max_turns=max_turns if max_turns is not None else MAX_TURNS,
            max_output_tokens=(
                max_output_tokens if max_output_tokens is not None
                else MAX_OUTPUT_TOKENS
            ),
            on_chunk=on_chunk,
        )
    except Exception as exc:
        import traceback
        stdout.write(f"Error: {exc}\n{traceback.format_exc()}\n")
        return 1
    if not verbose:
        stdout.write(f"{agent.last_text(history)}\n")
    else:
        # Plan M: pseudo-stream the final text if the provider did not.
        # The provider's on_chunk hook fires on every text delta. When the
        # provider doesn't yield text chunks (sync one-shot, fake providers
        # in tests, etc.), text_so_far is empty and we emit the answer in
        # tiny chunks with a small delay.
        final_text = agent.last_text(history)
        text_so_far = "".join(c.content for c in chunks if c.kind == "text")
        if final_text and not text_so_far:
            _pseudo_stream_text(final_text, on_chunk=on_chunk)
    return 0


def main(
    argv: list[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Entry point: flags, subcommands, -p one-shot, or the interactive shell."""
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    load_env()
    if not argv:
        raise SystemExit(
            run_repl(stdin=stdin, stdout=stdout, agent_factory=build_agent)
        )
    first = argv[0]
    if first in ("--version", "-V"):
        stdout.write(f"eaccode {__version__}\n")
        raise SystemExit(0)
    if first in ("--help", "-h"):
        stdout.write(f"{DESCRIPTION}\n\nUsage: eaccode [--version] [-p <prompt>] [command]\n")
        raise SystemExit(0)
    if first in ("-p", "--prompt"):
        if len(argv) < 2:
            stdout.write("Usage: eaccode -p <prompt> [--max-turns N] [--max-tokens N]\n")
            raise SystemExit(2)
        # Parse optional --max-turns / --max-tokens from the remaining args
        import argparse as _ap
        ap = _ap.ArgumentParser(prog="eaccode -p", add_help=False)
        ap.add_argument("prompt", nargs="+")
        ap.add_argument("--max-turns", type=int, default=None)
        ap.add_argument("--max-tokens", type=int, default=None)
        ap.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Stream tool calls inline as they happen.",
        )
        parsed = ap.parse_args(argv[1:])
        prompt = " ".join(parsed.prompt)
        raise SystemExit(_run_once(
            prompt, stdout,
            max_turns=parsed.max_turns,
            max_output_tokens=parsed.max_tokens,
            verbose=parsed.verbose,
        ))
    if first == "tui":
        from eaccode.tui import EaccodeApp

        EaccodeApp(agent_factory=build_agent).run()
        raise SystemExit(0)
    if first == "config":
        raise SystemExit(run_config_command(argv[1:], stdout=stdout, stdin=stdin))
    if first == "provider":
        raise SystemExit(run_provider_command(argv[1:], stdout=stdout))
    if first == "model":
        raise SystemExit(run_model_command(argv[1:], stdout=stdout))
    if first == "memory":
        raise SystemExit(run_memory_command(argv[1:], stdout=stdout))
    if first == "skill":
        raise SystemExit(run_skill_command(argv[1:], stdout=stdout))
    if first == "session":
        raise SystemExit(run_session_command(argv[1:], stdout=stdout))
    if first == "permissions":
        raise SystemExit(run_permissions_command(argv[1:], stdout=stdout))
    if first == "job":
        raise SystemExit(run_job_command(argv[1:], stdout=stdout))
    if first == "mcp":
        raise SystemExit(run_mcp_command(argv[1:], stdout=stdout))
    if first == "daemon":
        import contextlib

        from eaccode.cron import make_scheduler

        with contextlib.suppress(KeyboardInterrupt, SystemExit):
            make_scheduler().start()
        return 0
    stdout.write(f"Unknown command: {first} - try 'eaccode --help'\n")
    raise SystemExit(2)
