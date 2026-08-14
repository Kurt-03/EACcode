"""Slash palette (variante A): "/" opens a fuzzy overlay with all
commands and skills — arrow keys navigate, Enter inserts, Esc closes.

Implemented with prompt_toolkit's dropdown completion. Falls back to a
plain input() when stdin is not a real terminal (pipes, tests).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from eaccode import commands
from eaccode import skills as skills_mod

try:  # prompt_toolkit is a hard dependency; keep the import guarded anyway
    from prompt_toolkit import prompt as _pt_prompt
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.shortcuts import CompleteStyle
except ImportError:  # pragma: no cover - dependency always installed
    Completer = None  # type: ignore[assignment,misc]
    Completion = None  # type: ignore[assignment,misc]
    _pt_prompt = None  # type: ignore[assignment]


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


class _SlashCompleter(Completer):  # type: ignore[misc]
    """Completions for the current word when it starts with '/'."""

    def __init__(self, entries: list[tuple[str, str, bool]]) -> None:
        self._entries = entries

    def get_completions(self, document: Any, complete_event: Any) -> Iterable[Any]:
        word = document.get_word_before_cursor()
        if not word.startswith("/"):
            return
        query = word[1:]  # empty query shows every entry (palette opens at "/")
        for text, description, is_skill in self._entries:
            candidate = text[1:]  # compare without leading '/'
            if fuzzy_match(query, candidate):
                yield Completion(
                    text,
                    start_position=-len(word),
                    display_meta=("skill" if is_skill else description),
                )


def repl_prompt() -> str:
    """Read one input line with the slash palette on real terminals.

    Falls back to plain input() when stdin is not interactive (tests,
    pipes) or prompt_toolkit is unavailable.
    """
    import sys

    if not sys.stdin.isatty() or _pt_prompt is None:
        return input("eaccode> ")
    try:
        return _pt_prompt(
            "eaccode> ",
            completer=_SlashCompleter(palette_entries()),
            complete_while_typing=True,
            complete_style=CompleteStyle.MULTI_COLUMN,
        )
    except Exception:
        return input("eaccode> ")
