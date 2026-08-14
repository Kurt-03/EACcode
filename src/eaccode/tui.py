"""TUI (variante A, CC-Layout) — Textual app.

Chat scrolls at the top, the input is DOCKED at the bottom, and the slash
palette is pinned directly ABOVE the input (never floating mid-screen).
Slash commands + skills come from palette.palette_entries(); typing
filters, up/down move, enter picks AND runs, escape closes.

Agent calls run via ``@work(thread=True)``; results are posted back to the
UI thread. All agent/user text is markup-escaped before rendering.
"""

from __future__ import annotations

import contextlib
import io
from typing import Any

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.events import Key
from textual.markup import escape
from textual.message import Message
from textual.widgets import Footer, Input, Static

from eaccode import __version__, store
from eaccode import palette as palette_mod
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

USER_GLYPH = ">"
AGENT_GLYPH = "eaccode"

APP_CSS = """
#scroll {
    height: 1fr;
    border: round $primary;
    margin: 0 1;
}
#log {
    padding: 0 1;
}
#palette {
    dock: bottom;
    display: none;
    margin: 0 1 0 1;
    padding: 0 1;
}
#input {
    dock: bottom;
    margin: 0 1 1 1;
}
"""


class AgentResult(Message):
    """Carries an agent answer from the worker thread to the UI thread."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class PaletteOverlay(Static):
    """Borderless slash palette pinned above the input (no float)."""

    def __init__(self, entries: list[tuple[str, str, bool]] | None = None) -> None:
        super().__init__("", id="palette")
        self.entries = entries if entries is not None else palette_mod.palette_entries()
        self.selected = 0
        self.visible_state = False
        self._filtered: list[tuple[str, str, bool]] = []

    def refresh_for(self, text: str) -> None:
        if text.startswith("/"):
            query = text[1:]
            self._filtered = [
                entry
                for entry in self.entries
                if palette_mod.fuzzy_match(query, entry[0][1:])
            ]
            self.visible_state = True
            if self.selected >= len(self._filtered):
                self.selected = max(0, len(self._filtered) - 1)
        else:
            self._filtered = []
            self.visible_state = False
            self.selected = 0
        self.display = self.visible_state

    def move(self, delta: int) -> None:
        if not self._filtered:
            return
        self.selected = (self.selected + delta) % len(self._filtered)
        self.refresh()

    def selected_entry(self) -> tuple[str, str, bool] | None:
        if self.visible_state and self._filtered:
            return self._filtered[self.selected]
        return None

    def render(self) -> Text:
        text = Text()
        commands = [e for e in self._filtered if not e[2]]
        skills = [e for e in self._filtered if e[2]]
        index = 0
        for section, entries in (("Commands", commands), ("Skills", skills)):
            if not entries:
                continue
            if text:
                text.append("─" * 44 + "\n", style="dim")
            text.append(f"  {section}\n", style="bold dim")
            for name, description, _is_skill in entries:
                marker = "❯ " if index == self.selected else "  "
                if index == self.selected:
                    text.append(f"{marker}{name:<12} ", style="bold white on #005fb8")
                    text.append(description + "\n", style="#a8c8f0 on #005fb8")
                else:
                    text.append(f"{marker}{name:<12} ", style="white")
                    text.append(description + "\n", style="dim")
                index += 1
        if not self._filtered:
            text.append("  (no matches)\n", style="dim")
        return text


class EaccodeApp(App[None]):
    """Chat TUI: log at top, palette pinned above the input, input docked."""

    TITLE = "eaccode"
    CSS = APP_CSS
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(
        self,
        agent: Agent | None = None,
        agent_factory: Any | None = None,
        palette: bool = True,
    ) -> None:
        super().__init__()
        self._agent = agent
        self._agent_factory = agent_factory
        self._palette_enabled = palette
        self._chat_history: list[dict[str, Any]] = []
        self._log_text = ""
        self._session_id: str | None = None

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Static("", id="log"), id="scroll")
        yield PaletteOverlay()
        yield Input(placeholder="Ask eaccode... (type /)", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()

    # -- helpers ------------------------------------------------------------

    def _append(self, text: str) -> None:
        if not text:
            return
        self._log_text = f"{self._log_text}{text}\n" if self._log_text else text
        self.query_one("#log", Static).update(escape(self._log_text))
        with contextlib.suppress(Exception):
            self.query_one("#scroll", VerticalScroll).scroll_end(animate=False)

    def _get_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._agent_factory() if self._agent_factory else Agent()
            memory_block = injection_text()
            if memory_block:
                self._agent.system_prompt = f"{self._agent.system_prompt}\n\n{memory_block}"
        return self._agent

    def _set_overlay(self, visible: bool) -> None:
        overlay = self.query_one("#palette", PaletteOverlay)
        if not visible:
            overlay.visible_state = False
            overlay.display = False

    # -- input handling -----------------------------------------------------

    @staticmethod
    def _parse_command_line(text: str) -> tuple[str, list[str]]:
        try:
            parts = parse_args(text)
        except ValueError as exc:
            return "", [f"Error: {exc}"]
        return (parts[0] if parts else ""), parts[1:]

    def _handle_input(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if text.startswith("/"):
            self._run_slash(text[1:])
        else:
            self._append(f"{USER_GLYPH} {text}")
            self._run_agent(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            event.input.clear()
            return
        # first enter with "/" opens the palette instead of running
        if (
            self._palette_enabled
            and text.startswith("/")
            and not self.query_one("#palette", PaletteOverlay).visible_state
        ):
            self.query_one("#palette", PaletteOverlay).refresh_for(event.value)
            event.prevent_default()
            return
        event.input.clear()
        self._handle_input(text)

    @work(thread=True)
    def _run_agent(self, text: str) -> None:
        try:
            agent = self._get_agent()
            messages = list(self._chat_history) + [{"role": "user", "content": text}]
            history = agent.run(messages)
            answer = agent.last_text(history)
            new_messages = history[len(self._chat_history) + 1 :]
            self._chat_history[:] = history[1:]
            if self._session_id is not None:
                with contextlib.suppress(Exception):
                    for message in new_messages:
                        if message.get("role") in ("user", "assistant", "tool"):
                            store.add_message(
                                self._session_id,
                                str(message.get("role", "")),
                                str(message.get("content", "")),
                            )
        except Exception as exc:
            answer = f"Error: {exc}"
        self.post_message(AgentResult(answer))

    def on_agent_result(self, message: AgentResult) -> None:
        self._append(f"{AGENT_GLYPH}: {message.text}")

    # -- slash commands -----------------------------------------------------

    def _run_slash(self, command: str) -> None:
        name, args = self._parse_command_line(command)
        if name in ("exit", "quit"):
            self.exit()
            return
        if name == "clear":
            self._log_text = ""
            self._chat_history.clear()
            self.query_one("#log", Static).update("")
            return
        if name == "help":
            self._append(HELP_TEXT.rstrip())
            return
        if name == "version":
            self._append(f"eaccode {__version__}")
            return
        handlers = {
            "config": run_config_command,
            "provider": run_provider_command,
            "model": run_model_command,
            "memory": run_memory_command,
            "skill": run_skill_command,
            "session": run_session_command,
            "permissions": run_permissions_command,
            "job": run_job_command,
            "mcp": run_mcp_command,
        }
        handler = handlers.get(name)
        if handler is None:
            self._append(f"Unknown command: /{name} - type /help")
            return
        output = io.StringIO()
        if handler is run_config_command:
            handler(args, stdout=output, stdin=io.StringIO(""))
        else:
            handler(args, stdout=output)
        self._append(output.getvalue().rstrip())

    # -- palette key handling ----------------------------------------------

    def on_key(self, event: Key) -> None:
        if not self._palette_enabled:
            return
        overlay = self.query_one("#palette", PaletteOverlay)
        if not overlay.visible_state:
            return
        if event.key == "down":
            overlay.move(1)
            event.prevent_default()
        elif event.key == "up":
            overlay.move(-1)
            event.prevent_default()
        elif event.key == "escape":
            self._set_overlay(False)
            event.prevent_default()
        elif event.key == "enter":
            event.prevent_default()
            entry = overlay.selected_entry()
            self._set_overlay(False)
            if entry is not None:
                self._handle_input(entry[0])
