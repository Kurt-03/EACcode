"""Slash palette (variante 3, "Hermes-Flat"): "/" opens a borderless overlay
listing commands and skills — arrow keys move the selection, Enter picks,
Esc closes. Rendered as a custom prompt_toolkit application with a float
layer, so the look (highlight, separator, ❯ marker) is fully controlled.

Falls back to a plain input() when stdin is not a real terminal
(pipes, tests) or prompt_toolkit is unavailable.
"""

from __future__ import annotations

import sys
from typing import Any

from eaccode import commands
from eaccode import skills as skills_mod

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
        Window,
    )
    from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
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
        """Styled (style, text) lines; separator between commands and skills."""
        if not self.visible:
            return []
        lines: list[tuple[str, str]] = []
        commands = [e for e in self._filtered if not e[2]]
        skills = [e for e in self._filtered if e[2]]
        index = 0
        for section, entries in (("Commands", commands), ("Skills", skills)):
            if not entries:
                continue
            if lines:
                lines.append(("class:palette.separator", "─" * 44))
            lines.append(("class:palette.section", f"  {section}"))
            for entry in entries:
                name, description, _is_skill = entry
                marker = "❯" if index == self.selected else " "
                if index == self.selected:
                    lines.append(("class:palette.selected", f"{marker} {name:<12} "))
                    lines.append(("class:palette.selected.desc", description))
                else:
                    lines.append(("class:palette.normal", f"{marker} {name:<12} "))
                    lines.append(("class:palette.desc", description))
                lines.append(("", "\n"))
                index += 1
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
