"""Plain-text REPL box renderer (Plan M.2).

Claude-Code-style output for the plain-text REPL. Each ``on_chunk`` is
formatted as a discrete visual block:
- tool_start/tool_end/tool_error get ``⎿`` indents and a result line
- text/reasoning get a ``●`` turn-marker with progressive content
- errors get their own red ``✗`` block

This is a stateful renderer: it tracks the *current tool* so tool_start
and tool_end pair up cleanly.

Usage in REPL::

    render = ReplRenderer(stdout=sys.stdout)
    agent.run(messages, on_chunk=render)
    render.finish()  # emits the final summary footer
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from eaccode.providers.base import StreamChunk


# ANSI color codes (subset that works on Windows Terminal + most terminals)
class _A:
    RESET = "\x1b[0m"
    BOLD = "\x1b[1m"
    DIM = "\x1b[2m"
    CYAN = "\x1b[36m"
    GREEN = "\x1b[32m"
    RED = "\x1b[31m"
    YELLOW = "\x1b[33m"
    GRAY = "\x1b[90m"
    BLUE = "\x1b[34m"


class ReplRenderer:
    """Stateful plain-text renderer for the REPL.

    Tracks the *current tool block* so ``tool_start`` opens a box and
    ``tool_end`` closes it. ``reasoning`` chunks are emitted at the
    current indentation level (under the last turn marker).
    """

    def __init__(
        self,
        stdout: Any = None,
        plain: bool = False,
    ) -> None:
        self.stdout = stdout or sys.stdout
        self.plain = plain  # disable ANSI when piping
        self._turn_open = False       # have we printed "●" for this turn?
        self._current_tool_name: str | None = None
        self._current_tool_args: str = ""
        self._current_tool_box_open: bool = False
        self._turn_tools: list[str] = []   # names of tools in this turn
        self._turn_text_started = False    # did the model speak yet?

    # -- helpers ----------------------------------------------------------

    def _emit(self, s: str) -> None:
        self.stdout.write(s)
        self.stdout.flush()

    def _c(self, color: str, text: str) -> str:
        """Apply ANSI color (or pass through if plain)."""
        if self.plain:
            return text
        return f"{color}{text}{_A.RESET}"

    def _truncate(self, text: str, max_len: int = 80) -> str:
        """Compact display of a string, removing newlines."""
        flat = text.replace("\n", " ").replace("\r", " ")
        if len(flat) > max_len:
            return flat[: max_len - 1] + "…"
        return flat

    # -- turn lifecycle ---------------------------------------------------

    def begin_turn(self) -> None:
        """Print the ``●`` turn marker. Called before the first chunk."""
        if not self._turn_open:
            self._emit(f"{self._c(_A.BOLD, '●')} ")
            self._turn_open = True
            self._turn_text_started = False

    def finish(self, duration_s: float | None = None) -> None:
        """Print the final ``⏺ N tools used · Xs`` footer."""
        n = len(self._turn_tools)
        if n > 0:
            tool_word = "tool" if n == 1 else "tools"
            summary = f"⏺ {n} {tool_word} used"
            if duration_s is not None:
                summary += f" · {duration_s:.1f}s"
            self._emit(f"\n{self._c(_A.DIM, summary)}\n")
        else:
            # 0 tools — just duration
            if duration_s is not None:
                self._emit(f"\n{self._c(_A.DIM, f'⏺ {duration_s:.1f}s')}\n")
        # Reset for next turn
        self._turn_open = False
        self._current_tool_name = None
        self._current_tool_args = ""
        self._current_tool_box_open = False
        self._turn_tools = []
        self._turn_text_started = False

    # -- chunk dispatch ---------------------------------------------------

    def on_chunk(self, chunk: StreamChunk) -> None:
        """Receive one StreamChunk and format it."""
        kind = chunk.kind

        if kind == "text":
            self._handle_text(chunk)
        elif kind == "reasoning":
            self._handle_reasoning(chunk)
        elif kind == "tool_start":
            self._handle_tool_start(chunk)
        elif kind == "tool_end":
            self._handle_tool_end(chunk)
        elif kind == "tool_error":
            self._handle_tool_error(chunk)
        elif kind == "error":
            self._handle_error(chunk)
        elif kind == "done":
            pass  # silent - footer printed in finish()
        elif kind == "tool_call":
            # Raw tool_call from provider - usually wrapped in tool_start by agent
            pass

    # -- per-kind handlers -----------------------------------------------

    def _handle_text(self, chunk: StreamChunk) -> None:
        if not chunk.content:
            return
        self.begin_turn()
        self._emit(chunk.content)

    def _handle_reasoning(self, chunk: StreamChunk) -> None:
        if not chunk.content:
            return
        # Don't bother emitting standalone reasoning - Claude Code hides it
        # by default. We show it dimmed on a separate line if we've already
        # started emitting text (so it's an artifact, not a separate step).
        if self._turn_text_started:
            self._emit(self._c(_A.DIM, f"  💭 {chunk.content}"))

    def _handle_tool_start(self, chunk: StreamChunk) -> None:
        self.begin_turn()
        name = chunk.tool_name or "?"
        args = self._args_display(chunk.tool_args)
        icon = self._tool_icon(name)
        # If we were mid-text, finish the text line first
        if self._turn_text_started:
            self._emit("\n")
        if not self._current_tool_box_open:
            self._emit(f"  {self._c(_A.CYAN, '⎿')}  {icon} {self._c(_A.BOLD, name)} {args}\n")
            self._current_tool_name = name
            self._current_tool_args = args
            self._current_tool_box_open = True
            self._turn_tools.append(name)

    def _handle_tool_end(self, chunk: StreamChunk) -> None:
        if not self._current_tool_box_open:
            return
        result = self._truncate(chunk.tool_result or "(no result)", max_len=120)
        duration = chunk.tool_duration_ms
        timing = self._c(_A.DIM, f"  ✓ {duration}ms") if duration else ""
        self._emit(f"      {self._c(_A.DIM, result)}{timing}\n")
        self._current_tool_box_open = False
        self._current_tool_name = None

    def _handle_tool_error(self, chunk: StreamChunk) -> None:
        name = chunk.tool_name or "?"
        err = chunk.tool_error or "unknown error"
        duration = chunk.tool_duration_ms
        timing = f"  ({duration}ms)" if duration else ""
        if self._turn_text_started:
            self._emit("\n")
        self._emit(
            f"  {self._c(_A.RED, '⎿')}  {name}{timing}\n"
            f"      {self._c(_A.RED, '✗ ' + self._truncate(err, max_len=120))}\n"
        )
        self._current_tool_box_open = False

    def _handle_error(self, chunk: StreamChunk) -> None:
        # Top-level agent error (e.g. connection issue).
        # If we just finished a turn with a footer, do not start a new one;
        # the error belongs to that turn.
        if self._turn_open:
            # Turn is already open - emit error inline
            if self._turn_text_started:
                self._emit("\n")
            msg = self._truncate(chunk.content or "(unknown error)", max_len=200)
            self._emit(f"  {self._c(_A.RED, '✗')} {msg}\n")
        else:
            # No turn open - this is a standalone error
            msg = self._truncate(chunk.content or "(unknown error)", max_len=200)
            self._emit(f"{self._c(_A.RED, '✗ ' + msg)}\n")

    # -- formatters -------------------------------------------------------

    def _tool_icon(self, name: str) -> str:
        icons = {
            "read_file": "📖",
            "write_file": "✏️",
            "file_edit": "✏️",
            "list_files": "📂",
            "search_files": "🔍",
            "run_command": "⚙️",
            "spawn_subagent": "🧠",
        }
        return icons.get(name, "🔧")

    def _args_display(self, args: dict[str, Any]) -> str:
        """Compact ``key=value`` display. Redacts known secrets."""
        SECRET_KEYS = {"api_key", "password", "secret", "token", "auth"}
        if not args:
            return ""
        parts = []
        for k, v in args.items():
            if any(s in k.lower() for s in SECRET_KEYS):
                parts.append(f"{k}=***")
                continue
            s = str(v).replace("\n", " ")
            if len(s) > 60:
                s = s[:57] + "…"
            parts.append(f"{k}={s!r}")
        return " ".join(parts)


__all__ = ["ReplRenderer", "_A"]
