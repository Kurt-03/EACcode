"""Slash palette (variante 3, "Hermes-Flat"): "/" opens a borderless overlay
listing commands and skills — arrow keys move the selection, Enter picks,
Esc closes. Rendered as a custom prompt_toolkit application with a float
layer, so the look (highlight, separator, ❯ marker) is fully controlled.

Falls back to a plain input() when stdin is not a real terminal
(pipes, tests) or prompt_toolkit is unavailable.
"""

from __future__ import annotations

import contextlib
import io
import sys
import threading
import time
from pathlib import Path
from typing import Any

from eaccode import __version__, commands, store
from eaccode import skills as skills_mod
from eaccode.banner import model_label, render_banner
from eaccode.banner import quiet as banner_quiet
from eaccode.banner import status_line as render_status_line

try:
    from prompt_toolkit.application import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
    from prompt_toolkit.key_binding.bindings.basic import load_basic_bindings
    from prompt_toolkit.key_binding.bindings.emacs import load_emacs_bindings
    from prompt_toolkit.layout import (
        Dimension,
        Float,
        FloatContainer,
        HSplit,
        Layout,
        ScrollOffsets,
        Window,
    )
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    from prompt_toolkit.layout.processors import BeforeInput
    from prompt_toolkit.styles import Style
except ImportError:  # pragma: no cover - dependency always installed
    Application = None  # type: ignore[assignment,misc]


def palette_entries() -> list[tuple[str, str, bool]]:
    """(text, description, is_skill) for the palette: commands + skills."""
    entries: list[tuple[str, str, bool]] = []
    for line in commands.HELP_TEXT.splitlines():
        stripped = line.strip()
        if stripped.startswith("/") and "  " in stripped:
            name, _, description = stripped.partition("  ")
            entries.append((name.split()[0], description.strip(), False))
    try:
        for skill in skills_mod.list_skills():
            entries.append((f"/{skill['name']}", f"skill ({skill['trigger']})", True))
    except Exception:
        pass  # palette works without skills
    return entries


def fuzzy_match(query: str, text: str) -> bool:
    """Subsequence fuzzy match (case-insensitive)."""
    query = query.lower()
    text = text.lower()
    index = 0
    for char in query:
        index = text.find(char, index)
        if index < 0:
            return False
        index += 1
    return True


STYLE = Style.from_dict(
    {
        "palette.normal": "fg:#d4d4d4",
        "palette.name": "bold fg:#ffffff",
        "palette.desc": "fg:#6e6e6e",
        "palette.selected": "bg:#005fb8 fg:#ffffff bold",
        "palette.selected.desc": "bg:#005fb8 fg:#a8c8f0",
        "palette.separator": "fg:#3f3f46",
        "palette.section": "fg:#8b8b8b",
    }
)


class PalettePrompt:
    """Borderless slash palette rendered as a prompt_toolkit float."""

    def __init__(self, entries: list[tuple[str, str, bool]] | None = None) -> None:
        self.entries = entries if entries is not None else palette_entries()
        self.buffer = Buffer()
        self.selected = 0
        self.visible = False
        self._filtered: list[tuple[str, str, bool]] = []

    # -- filter logic (unit-testable) -------------------------------------
    def refresh(self, text: str) -> None:
        if text.startswith("/"):
            query = text[1:]
            self._filtered = [
                entry for entry in self.entries if fuzzy_match(query, entry[0][1:])
            ]
            self.visible = True
            if self.selected >= len(self._filtered):
                self.selected = max(0, len(self._filtered) - 1)
        else:
            self._filtered = []
            self.visible = False
            self.selected = 0

    def move(self, delta: int) -> None:
        if not self._filtered:
            return
        count = len(self._filtered)
        self.selected = (self.selected + delta) % count

    def accept(self) -> str | None:
        """Return the chosen entry text, or None when nothing is selected."""
        if self.visible and self._filtered:
            return self._filtered[self.selected][0]
        return None

    # -- rendering --------------------------------------------------------
    def _render_lines(self) -> list[tuple[str, str]]:
        """Styled (style, text) lines; flat list with aligned columns."""
        if not self.visible:
            return []
        lines: list[tuple[str, str]] = []
        # dynamic column width: align all names to the longest one
        max_name = max((len(e[0]) for e in self._filtered), default=0)
        for index, entry in enumerate(self._filtered):
            name, description, _is_skill = entry
            marker = "❯ " if index == self.selected else "  "
            col = f"{marker}{name:<{max_name + 2}}"
            if index == self.selected:
                lines.append(("class:palette.selected", col))
                lines.append(("class:palette.selected.desc", description))
            else:
                lines.append(("class:palette.normal", col))
                lines.append(("class:palette.desc", description))
            lines.append(("", "\n"))
        if not lines:
            lines.append(("class:palette.desc", "  (no matches)"))
        return lines

    def _float(self) -> Float:
        control = FormattedTextControl(self._render_lines)
        return Float(Window(control, height=Dimension()), allow_cover_cursor=False)

    # -- application ------------------------------------------------------
    def build_application(self, input: Any = None, output: Any = None) -> Application[str]:
        custom = KeyBindings()

        @custom.add("down", eager=True)
        def _down(event: Any) -> None:
            if self.visible:
                self.move(1)
            else:
                event.current_buffer.cursor_down()

        @custom.add("up", eager=True)
        def _up(event: Any) -> None:
            if self.visible:
                self.move(-1)
            else:
                event.current_buffer.cursor_up()

        @custom.add("escape", eager=True)
        def _escape(event: Any) -> None:
            if self.visible:
                self.visible = False
            else:
                event.app.exit(result="")

        @custom.add("enter", eager=True)
        def _enter(event: Any) -> None:
            choice = self.accept()
            if choice is not None:
                event.current_buffer.text = choice
            event.app.exit(result=event.current_buffer.text)

        kb = merge_key_bindings(
            [custom, load_basic_bindings(), load_emacs_bindings()]
        )

        def _on_text_changed(_buffer: Buffer) -> None:
            self.refresh(self.buffer.text)

        self.buffer.on_text_changed += _on_text_changed

        root = FloatContainer(
            content=HSplit(
                [Window(BufferControl(buffer=self.buffer), wrap_lines=False)]
            ),
            floats=[self._float()],
        )
        return Application(
            layout=Layout(root, focused_element=self.buffer),
            key_bindings=kb,
            style=STYLE,
            input=input,
            output=output,
        )

    def run(self) -> str:
        return self.build_application().run()


def repl_prompt() -> str:
    """Read one input line with the flat slash palette on real terminals."""
    if not sys.stdin.isatty() or Application is None:
        return input("eaccode> ")
    try:
        return PalettePrompt().run()
    except Exception:
        return input("eaccode> ")


class ChatApp:
    """Fullscreen chat REPL (Hermes style, variant A-REPL).

    Log at the top (auto-scroll), slash palette pinned ABOVE the input,
    input docked at the bottom. Same prompt_toolkit stack as the palette;
    the stream REPL stays for pipes/scripts. Agent calls run in a worker
    thread; permission prompts are answered inline (y/N in the input).
    """

    STYLE = Style.from_dict(
        {
            "chat.user": "bold #4fc1ff",
            "chat.agent": "bold white",
            "chat.error": "bold #ff6b6b",
            "chat.permission": "bold #ffd166",
            "chat.stat": "fg:#6e6e6e",
            "chat.banner": "fg:#9a9a9a",
            "chat.prompt": "bold #4fc1ff",
            "palette.normal": "fg:#d4d4d4",
            "palette.name": "bold fg:#ffffff",
            "palette.desc": "fg:#6e6e6e",
            "palette.selected": "bg:#005fb8 fg:#ffffff bold",
            "palette.selected.desc": "bg:#005fb8 fg:#a8c8f0",
            "palette.separator": "fg:#3f3f46",
            "palette.section": "fg:#8b8b8b",
        }
    )

    def __init__(
        self,
        agent: Any | None = None,
        agent_factory: Any | None = None,
    ) -> None:
        self._agent = agent
        self._agent_factory = agent_factory
        self._chat_history: list[dict[str, Any]] = []
        self._log_lines: list[tuple[str, str]] = []
        self._buffer = Buffer()
        self._app: Application[str] | None = None
        self.palette = PalettePrompt()
        self._session_id: str | None = None
        self._permission_prompt: str | None = None
        self._permission_event = threading.Event()
        self._permission_answer = "n"
        self._stream_open = False
        self._streamed_any = False

    # -- log ---------------------------------------------------------------

    def _append(self, style: str, text: str) -> None:
        self._log_lines.append((style, text + "\n"))
        if self._app is not None:
            self._app.invalidate()

    # -- agent -------------------------------------------------------------

    def _get_agent(self) -> Any:
        if self._agent is None:
            self._agent = self._agent_factory() if self._agent_factory else None
            self._wire_agent_gate(self._agent)
        return self._agent

    def _run_agent(self, text: str) -> None:
        threading.Thread(target=self._agent_worker, args=(text,), daemon=True).start()

    def _on_token(self, delta: str) -> None:
        """Stream callback (worker thread): extend the open log line."""
        if delta == "":
            self._stream_open = False  # round marker: next text starts fresh
            return
        self._streamed_any = True
        if not self._stream_open:
            # open a fresh agent line (append ignores empty text)
            self._log_lines.append(("class:chat.agent", ""))
            self._stream_open = True
        style, text = self._log_lines[-1]
        self._log_lines[-1] = (style, text + delta)
        if self._app is not None:
            self._app.invalidate()

    def _agent_worker(self, text: str) -> None:
        start = time.monotonic()
        self._streamed_any = False
        try:
            agent = self._get_agent()
            if agent is None:
                answer = "Error: no agent available"
            else:
                messages = list(self._chat_history) + [
                    {"role": "user", "content": text}
                ]
                history = agent.run(
                    messages, on_token=self._on_token
                )
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
        self._stream_open = False
        if self._streamed_any:
            # streamed text is already in the log line by line; only drop a
            # line that stayed empty (e.g. a tool-only round)
            if self._log_lines and self._log_lines[-1] == ("class:chat.agent", ""):
                self._log_lines.pop()
            if self._app is not None:
                self._app.invalidate()
        elif answer:
            self._append("class:chat.agent", answer)
        try:
            from eaccode import config as cfg

            self._append(
                "class:chat.stat",
                render_status_line(
                    model_label(cfg.load_config()),
                    time.monotonic() - start,
                    len(answer),
                ),
            )
        except Exception:
            pass

    # -- permission (inline) ------------------------------------------------

    def _ask(self, prompt: str) -> bool:
        self._permission_prompt = prompt
        self._permission_event.clear()
        self._append("class:chat.permission", f"Allow: {prompt} [y/N]")
        self._permission_event.wait(timeout=600)
        return self._permission_answer in ("y", "yes")

    def _wire_permission(self) -> None:
        """Wire the inline ask into the tool wrapper (run_command gate)."""
        with contextlib.suppress(Exception):
            from eaccode import tools

            tools.permission_handler = lambda command: self._ask(command)

    def _wire_agent_gate(self, agent: Any) -> None:
        """Wire the inline ask into the agent's permission manager."""
        manager = getattr(agent, "permission_manager", None)
        if manager is not None:
            manager.ask_handler = lambda name, arguments: self._ask(
                f"{name} {arguments}"
            )

    # -- input -------------------------------------------------------------

    def _submit(self, text: str) -> bool:
        """Handle one submitted line; returns True when it was consumed."""
        text = text.strip()
        if not text:
            return True
        if self._permission_prompt is not None:
            self._permission_answer = text.lower() or "n"
            self._permission_prompt = None
            self._permission_event.set()
            return True
        if text.startswith("/") and not self.palette.visible:
            self.palette.refresh(text)  # first enter opens the palette
            return False  # keep the text in the buffer
        if self.palette.visible:
            choice = self.palette.accept()
            self.palette.visible = False
            if choice is not None:
                text = choice
            # no match: run the typed text itself (e.g. unknown command)
        self._append("class:chat.user", f"> {text}")
        if text.startswith("/"):
            self._run_slash(text[1:])
        else:
            self._run_agent(text)
        return True

    def _run_slash(self, command: str) -> None:
        name, args = self._parse(command)
        if name in ("exit", "quit"):
            if self._app is not None:
                self._app.exit(result="")
            return
        if name == "clear":
            self._log_lines.clear()
            return
        if name == "help":
            self._append("", commands.HELP_TEXT.rstrip())
            return
        if name == "version":
            self._append("", f"eaccode {__version__}")
            return
        handlers = {
            "config": commands.run_config_command,
            "provider": commands.run_provider_command,
            "model": commands.run_model_command,
            "memory": commands.run_memory_command,
            "skill": commands.run_skill_command,
            "session": commands.run_session_command,
            "permissions": commands.run_permissions_command,
            "job": commands.run_job_command,
            "mcp": commands.run_mcp_command,
        }
        handler = handlers.get(name)
        if handler is None:
            self._append("class:chat.error", f"Unknown command: /{name} - type /help")
            return
        output = io.StringIO()
        if handler is commands.run_config_command:
            handler(args, stdout=output, stdin=io.StringIO(""))
        else:
            handler(args, stdout=output)
        self._append("", output.getvalue().rstrip())

    @staticmethod
    def _parse(command: str) -> tuple[str, list[str]]:
        try:
            parts = commands.parse_args(command)
        except ValueError as exc:
            return "", [f"Error: {exc}"]
        return (parts[0] if parts else ""), parts[1:]

    # -- application --------------------------------------------------------

    def _log_control(self) -> FormattedTextControl:
        return FormattedTextControl(lambda: list(self._log_lines))

    def _palette_control(self) -> FormattedTextControl:
        return FormattedTextControl(lambda: self.palette._render_lines())

    def build_application(
        self, input: Any = None, output: Any = None
    ) -> Application[str]:
        custom = KeyBindings()

        def _on_text_changed(_buffer: Buffer) -> None:
            self.palette.refresh(self._buffer.text)

        self._buffer.on_text_changed += _on_text_changed

        @custom.add("enter", eager=True)
        def _enter(event: Any) -> None:
            if self._submit(event.current_buffer.text):
                event.current_buffer.text = ""

        @custom.add("up", eager=True)
        def _up(event: Any) -> None:
            if self.palette.visible:
                self.palette.move(-1)
            else:
                event.current_buffer.cursor_up()

        @custom.add("down", eager=True)
        def _down(event: Any) -> None:
            if self.palette.visible:
                self.palette.move(1)
            else:
                event.current_buffer.cursor_down()

        @custom.add("escape", eager=True)
        def _escape(event: Any) -> None:
            if self.palette.visible:
                self.palette.visible = False

        @custom.add("c-c", eager=True)
        def _ctrl_c(event: Any) -> None:
            event.app.exit(result="")

        kb = merge_key_bindings(
            [custom, load_basic_bindings(), load_emacs_bindings()]
        )
        input_row = Window(
            BufferControl(
                buffer=self._buffer,
                input_processors=[BeforeInput([("class:chat.prompt", "❯ ")])],
            ),
            height=1,
        )
        palette_win = Window(
            self._palette_control(),
            height=Dimension(max=12),
            dont_extend_height=True,
        )
        root = HSplit(
            [
                Window(
                    self._log_control(),
                    wrap_lines=True,
                    scroll_offsets=ScrollOffsets(bottom=10**8),
                ),
                input_row,
                palette_win,
            ]
        )
        self._app = Application(
            layout=Layout(root, focused_element=self._buffer),
            key_bindings=kb,
            style=self.STYLE,
            input=input,
            output=output,
        )
        return self._app

    def run(self) -> str:
        with contextlib.suppress(Exception):
            from eaccode import store as _store

            self._session_id = _store.new_session()
        if not banner_quiet() and not self._log_lines:
            try:
                from eaccode import config as cfg

                self._append(
                    "class:chat.banner",
                    render_banner(
                        cfg.load_config(),
                        session_id=self._session_id,
                        cwd=str(Path.cwd()),
                    ),
                )
            except Exception:
                pass
        self._wire_permission()
        return self.build_application().run()
