"""Clarify tool (Phase G.4, Plan G v5).

Lets the model ask the user a multiple-choice question instead of
guessing. Useful when an ambiguity would otherwise force the model to
hallucinate.

Mirrors tools/clarify_tool.py from Hermes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class ClarifyChoice:
    label: str
    description: str = ""


@dataclass
class ClarifyResult:
    selected: list[str]   # selected labels
    multi_select: bool
    raw: str              # raw user input


def _flatten_choice(c: ClarifyChoice | str) -> str:
    if isinstance(c, ClarifyChoice):
        return c.label
    return c


def invoke_callback(
    callback: Callable[..., str | None] | None,
    question: str,
    choices: list[ClarifyChoice],
    multi_select: bool,
) -> ClarifyResult | None:
    """Call a registered UI callback to ask the user."""
    if callback is None:
        return None
    raw = callback(
        question=question,
        choices=choices,
        multi_select=multi_select,
    )
    if raw is None:
        return None
    selected = _parse_multi_select_response(raw)
    return ClarifyResult(selected=selected, multi_select=multi_select, raw=raw)


def _parse_multi_select_response(raw_response: str) -> list[str]:
    """Parse the user's reply into a list of selected labels.

    Accepts comma-separated entries ("a, c") or numeric positions
    ("1, 3"). Whitespace is trimmed. Empty reply returns [].
    """
    if not raw_response:
        return []
    parts = [p.strip() for p in raw_response.split(",") if p.strip()]
    return parts


def check_clarify_requirements() -> bool:
    """Whether the runtime can present clarify questions.

    Always returns True for the CLI fallback; the REPL overrides this
    when a richer UI is wired up.
    """
    return True


def fallback_cli_prompt(
    question: str,
    choices: list[ClarifyChoice | str],
    multi_select: bool = False,
) -> str:
    """Render a minimal CLI prompt and read a line from stdin.

    Used when the REPL has not registered a richer UI callback.
    """
    import sys

    print(f"\n[clarify] {question}")
    for i, choice in enumerate(choices, 1):
        label = _flatten_choice(choice)
        desc = (
            choice.description
            if isinstance(choice, ClarifyChoice)
            else ""
        )
        print(f"  {i}. {label}" + (f"  ({desc})" if desc else ""))
    if multi_select:
        print("(comma-separated, e.g. '1, 3')")
    else:
        print("(single choice, e.g. '1')")
    try:
        line = input("> ").strip()
    except EOFError:
        return ""
    return line


__all__ = [
    "ClarifyChoice",
    "ClarifyResult",
    "check_clarify_requirements",
    "fallback_cli_prompt",
    "invoke_callback",
]
