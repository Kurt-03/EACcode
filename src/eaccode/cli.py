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


def build_agent() -> Agent:
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
        if model_id and provider_config:
            provider_name, _, _ = model_id.partition("/")
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
    return Agent(
        tools=tools,
        system_prompt=system_prompt,
        permission_manager=permission_manager,
    )


def _run_once(prompt: str, stdout: TextIO) -> int:
    """Non-interactive mode: one user message, print the answer."""
    agent = build_agent()
    try:
        history = agent.run([{"role": "user", "content": prompt}])
    except Exception as exc:
        stdout.write(f"Error: {exc}\n")
        return 1
    stdout.write(f"{agent.last_text(history)}\n")
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
            stdout.write("Usage: eaccode -p <prompt>\n")
            raise SystemExit(2)
        raise SystemExit(_run_once(" ".join(argv[1:]), stdout))
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
