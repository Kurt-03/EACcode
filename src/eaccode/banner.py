"""Startup banner (Hermes style): ASCII logo + status box + status line.

Shown on interactive terminals and as the first lines of the fullscreen
chat log. Suppress everywhere with ``EACCODE_QUIET=1`` (Hermes -Q parity).
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from eaccode import __version__

LOGO = """\
███████╗ █████╗  ██████╗ ██████╗  ██████╗ ██████╗ ███████╗
██╔════╝██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██╔═══██╗██╔════╝
█████╗  ███████║██║     ██║      ██║   ██║██║   ██║█████╗
██╔══╝  ██╔══██║██║     ██║      ██║   ██║██║   ██║██╔══╝
███████╗██║  ██║╚██████╗╚██████╗ ╚██████╔╝╚██████╔╝███████╗
╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝"""

WELCOME = "Welcome to eaccode! Type your message or /help for commands."
TIP = "✦ Tip: /memory stores durable facts - eaccode remembers them across sessions."


def quiet() -> bool:
    """True when the banner must be suppressed (EACCODE_QUIET=1)."""
    return os.environ.get("EACCODE_QUIET") == "1"


def model_label(conf: dict[str, Any]) -> str:
    """Human label for the configured model, e.g. 'MiniMax-M3 (minimax)'."""
    default = conf.get("model", {}).get("default") or "--"
    if "/" in default:
        provider, name = default.split("/", 1)
        return f"{name} ({provider})"
    return default


def count_skills() -> int:
    try:
        from eaccode import skills

        return len(skills.list_skills())
    except Exception:
        return 0


def count_tools() -> int:
    """Total agent tools: builtin + all feature factories."""
    try:
        from eaccode import tools
        from eaccode.editing import make_editing_tools
        from eaccode.git import make_git_tools
        from eaccode.learning import make_learning_tools
        from eaccode.memory import make_memory_tools
        from eaccode.repo import make_repo_tools
        from eaccode.testrunner import make_test_tools

        return (
            len(tools.BUILTIN_TOOLS)
            + len(make_repo_tools())
            + len(make_editing_tools())
            + len(make_git_tools())
            + len(make_test_tools())
            + len(make_memory_tools())
            + len(make_learning_tools())
        )
    except Exception:
        return 0


def mcp_labels(conf: dict[str, Any]) -> list[str]:
    servers = conf.get("mcp", {}).get("servers", {})
    return [
        f"{name} ({entry.get('transport', 'stdio')})"
        for name, entry in servers.items()
        if isinstance(entry, dict)
    ]


def _box_width() -> int:
    try:
        width = shutil.get_terminal_size().columns
    except Exception:
        width = 80
    return max(60, min(width - 2, 88))


def render_banner(
    conf: dict[str, Any],
    session_id: str | None = None,
    cwd: str | None = None,
) -> str:
    """Full startup banner: logo, status box, welcome line, tip."""
    width = _box_width()
    line = "─" * (width - 2)
    model = model_label(conf)
    tools = count_tools()
    skills = count_skills()
    mcp = mcp_labels(conf)
    session = session_id or "--"

    def row(text: str = "") -> str:
        return f"│  {text:<{width - 6}} │"

    header = f" eaccode {__version__} · {model} · {cwd or '--'} "
    box = [
        f"╭─{header}{'─' * max(0, width - 2 - len(header))}╮",
        row(f"Session: {session}"),
        row(f"Available Tools: {tools}"),
    ]
    if mcp:
        box.append(row(f"MCP Servers: {', '.join(mcp)}"))
    if skills:
        box.append(row(f"Available Skills: {skills}"))
    box.append(row())
    box.append(
        f"│  {tools} tools · {skills} skills · /help for commands  ".ljust(width - 1)
        + "│"
    )
    box.append(f"╰─{line}╯")
    return "\n".join([LOGO, "", *box, "", WELCOME, TIP])


def status_line(model: str, seconds: float = 0.0, chars: int = 0) -> str:
    """Compact line after an answer: model, duration, output size."""
    if seconds:
        return f"⚕ {model} │ {seconds:.1f}s │ {chars} chars"
    return f"⚕ {model} │ ready"
