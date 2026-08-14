"""TUI skeleton (Phase A8) — Textual app.

A chat surface with role glyphs (Hermes style), slash commands and a worker
thread for agent calls so the UI never blocks. Agent calls run via
``@work(thread=True)`` and post results back to the UI thread.
"""

from __future__ import annotations

import io
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Footer, Input, Static

from eaccode import __version__
from eaccode.agent import Agent
from eaccode.commands import (
    run_config_command,
    run_memory_command,
    run_model_command,
    run_provider_command,
)
from eaccode.memory import injection_text
from eaccode.repl import HELP_TEXT

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


class EaccodeApp(App[None]):
    """Chat TUI: input at the bottom, log above, slash commands included."""

    TITLE = "eaccode"
    CSS = APP_CSS
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def __init__(
        self,
        agent: Agent | None = None,
        agent_factory: Any | None = None,
    ) -> None:
        super().__init__()
        self._agent = agent
        self._agent_factory = agent_factory
        self._chat_history: list[dict[str, Any]] = []
        self._log_text = ""

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Static("", id="log"), id="scroll")
        yield Input(placeholder="Ask eaccode... (type /help)", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#input", Input).focus()

    # -- helpers ------------------------------------------------------------

    def _append(self, text: str) -> None:
        if not text:
            return
        self._log_text = f"{self._log_text}{text}\n" if self._log_text else text
        self.query_one("#log", Static).update(self._log_text)

    def _get_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._agent_factory() if self._agent_factory else Agent()
            memory_block = injection_text()
            if memory_block:
                self._agent.system_prompt = f"{self._agent.system_prompt}\n\n{memory_block}"
        return self._agent

    # -- input handling -----------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.clear()
        if not text:
            return
        if text.startswith("/"):
            self._run_slash(text[1:])
        else:
            self._append(f"{USER_GLYPH} {text}")
            self._run_agent(text)

    def _run_slash(self, command: str) -> None:
        name = command.split()[0] if command else ""
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
        }
        handler = handlers.get(name)
        if handler is None:
            self._append(f"Unknown command: /{name} - type /help")
            return
        output = io.StringIO()
        handler(command.split()[1:], stdout=output)
        self._append(output.getvalue().rstrip())

    # -- agent worker -------------------------------------------------------

    @work(thread=True)
    def _run_agent(self, text: str) -> None:
        try:
            agent = self._get_agent()
            messages = list(self._chat_history) + [{"role": "user", "content": text}]
            history = agent.run(messages)
            answer = agent.last_text(history)
            self._chat_history[:] = history[1:]
        except Exception as exc:
            answer = f"Error: {exc}"
        self.post_message(AgentResult(answer))

    def on_agent_result(self, message: AgentResult) -> None:
        self._append(f"{AGENT_GLYPH}: {message.text}")
