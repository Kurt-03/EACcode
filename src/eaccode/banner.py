"""Startup banner (Hermes style): ASCII logo + status box + status line.

Shown on interactive terminals and as the first lines of the fullscreen
chat log. Suppress everywhere with ``EACCODE_QUIET=1`` (Hermes -Q parity).
"""

from __future__ import annotations

import os
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


def render_banner(
    conf: dict[str, Any],
    session_id: str | None = None,
    cwd: str | None = None,
) -> str:
    """Full startup banner: logo, status box, welcome line, tip.

    The box sizes itself to its content so every wall line has the same
    width - it never gets clipped by a narrower terminal window.
    """
    model = model_label(conf)
    tools = count_tools()
    skills = count_skills()
    mcp = mcp_labels(conf)
    session = session_id or "--"

    rows = [f"Session: {session}", f"Available Tools: {tools}"]
    if mcp:
        rows.append(f"MCP Servers: {', '.join(mcp)}")
    if skills:
        rows.append(f"Available Skills: {skills}")
    footer = f"{tools} tools · {skills} skills · /help for commands"
    header = f" eaccode {__version__} · {model} · {cwd or '--'} "
    content_width = max(len(row_text) for row_text in rows + [footer])
    # box width follows the longest content OR the header, whichever is wider
    width = max(content_width + 6, len(header) + 3)

    def row(text: str = "") -> str:
        return f"│  {text:<{width - 6}}  │"

    box = [
        f"╭─{header}{'─' * (width - len(header) - 3)}╮",
        *[row(text) for text in rows],
        row(),
        row(footer),
        f"╰─{'─' * (width - 3)}╯",
    ]
    return "\n".join([LOGO, "", *box, "", WELCOME, TIP])


def status_line(
    model: str,
    seconds: float = 0.0,
    chars: int = 0,
    *,
    warning: str | None = None,
    exit_code: int | None = None,
) -> str:
    """Compact line after an answer: model, duration, output size.

    Phase B.1: include a `⚠` warning marker when the last tool returned
    a non-zero exit code (or set `warning=`).
    """
    base = f"{model} │ {seconds:.1f}s │ {chars} chars" if seconds else f"{model} │ ready"
    if exit_code is not None and exit_code != 0:
        base = f"{base} │ ⚠ exit={exit_code}"
    elif warning:
        base = f"{base} │ ⚠ {warning}"
    return base
