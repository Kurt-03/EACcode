"""Persistent agent memory: MEMORY.md / USER.md (Phase A6).

Two curated markdown files in the data directory:
- MEMORY.md: agent-curated facts and lessons (the agent writes these)
- USER.md:   facts about the user (preferences, corrections)

The agent's system prompt is extended with both files at chat start.
"""

from __future__ import annotations

from pathlib import Path

from eaccode import config as cfg

MEMORY_FILE_NAME = "MEMORY.md"
USER_FILE_NAME = "USER.md"


def memory_dir() -> Path:
    """Directory holding the memory files (data dir)."""
    return cfg.data_dir()


def memory_path() -> Path:
    return memory_dir() / MEMORY_FILE_NAME


def user_path() -> Path:
    return memory_dir() / USER_FILE_NAME


def read_file(target: Path) -> str:
    """Return file content, or the empty string when missing."""
    try:
        return target.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def add_entry(target: Path, text: str) -> str:
    """Append ``- text`` to the file; returns a confirmation."""
    text = text.strip()
    if not text:
        return "Error: empty entry"
    lines = read_file(target)
    entry = f"- {text}"
    lines = f"{lines}\n{entry}" if lines else entry
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(lines + "\n", encoding="utf-8")
    except OSError as exc:
        return f"Error: cannot write memory: {exc}"
    return "ok"


def remove_entry(target: Path, substring: str) -> str:
    """Remove lines containing substring; returns a confirmation."""
    lines = read_file(target)
    if not lines:
        return "Error: memory is empty"
    kept = [line for line in lines.splitlines() if substring not in line]
    if len(kept) == len(lines.splitlines()):
        return f"Error: no entry contains: {substring}"
    try:
        target.write_text("\n".join(kept) + "\n", encoding="utf-8")
    except OSError as exc:
        return f"Error: cannot write memory: {exc}"
    return "ok"


def injection_text() -> str:
    """Build the memory block appended to the agent's system prompt."""
    memory = read_file(memory_path())
    user = read_file(user_path())
    sections: list[str] = []
    if memory:
        sections.append("## Agent Memory (facts you have learned)\n" + memory)
    if user:
        sections.append("## About the User\n" + user)
    return "\n\n".join(sections)
