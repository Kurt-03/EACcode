"""Diff editing (Phase D2): fuzzy patching, syntax checks, rollback.

Tools for the agent:
- ``patch_file``: replace old text with new text (exact or fuzzy match)
- ``patch_multiple``: several atomic edits across files in one call
- ``undo_edit``: roll back the most recent edits (backup stack)

Every write is backed up first (data/edits/), so rollback is always
possible. Python files get a syntax check after every edit.
"""

from __future__ import annotations

import difflib
import os
import py_compile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eaccode import config as cfg
from eaccode.agent import Tool

FUZZY_THRESHOLD = 0.85
MAX_UNDO = 20
SYNTAX_MAX_CHARS = 200_000


# Module-level workspace. Initialised lazily; tests can override.
_workspace = None


def _get_workspace():
    """Return the module workspace, loading from config on first call."""
    global _workspace
    if _workspace is None:
        from eaccode.workspace import load_workspace_from_config
        _workspace = load_workspace_from_config()
    return _workspace


def _set_workspace(ws_obj) -> None:
    global _workspace
    _workspace = ws_obj


@dataclass
class EditResult:
    ok: bool
    message: str


class EditError(Exception):
    """Raised when a patch cannot be applied."""


def _backup_dir() -> Path:
    return cfg.data_dir() / "edits"


class EditSession:
    """Rollback stack: each edit stores a backup before overwriting."""

    def __init__(self) -> None:
        self._stack: list[tuple[Path, Path]] = []

    def backup(self, target: Path) -> None:
        target = target.resolve()
        session = _backup_dir() / str(os.getpid())
        session.mkdir(parents=True, exist_ok=True)
        backup = session / f"{len(self._stack):04d}-{target.name}.bak"
        backup.write_bytes(target.read_bytes())
        self._stack.append((target, backup))
        if len(self._stack) > MAX_UNDO:
            _, oldest = self._stack.pop(0)
            with __import__("contextlib").suppress(OSError):
                oldest.unlink()

    def undo(self) -> str:
        if not self._stack:
            return "Error: nothing to undo"
        target, backup = self._stack.pop()
        if backup.exists():
            target.write_bytes(backup.read_bytes())
        return f"reverted {target.name}"

    def __len__(self) -> int:
        return len(self._stack)


_session: EditSession = EditSession()


def syntax_check(path: Path) -> str | None:
    """Return an error message for broken Python syntax, else None."""
    if path.suffix != ".py":
        return None
    if path.stat().st_size > SYNTAX_MAX_CHARS:
        return None
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        return f"syntax error in {path.name}: {exc}"
    return None


def _find_fuzzy(haystack: str, needle: str) -> int:
    """Find the start index of the closest fuzzy match (>= threshold).

    Character-level comparison over sliding windows (stepped for speed).
    """
    best: tuple[float, int] = (0.0, -1)
    hay_len = len(haystack)
    needle_len = len(needle)
    if needle_len == 0 or needle_len > hay_len:
        return -1
    step = max(1, needle_len // 8)
    for start in range(0, hay_len - needle_len + 1, step):
        candidate = haystack[start : start + needle_len]
        ratio = difflib.SequenceMatcher(None, candidate, needle).ratio()
        if ratio > best[0]:
            best = (ratio, start)
    if best[0] >= FUZZY_THRESHOLD:
        return best[1]
    return -1


def _apply_fuzzy(content: str, old: str, new: str) -> str:
    """Line-based fuzzy substitution: replace the matched lines with new.

    old and new must have the same number of lines; the matched block is
    verified against the fuzzy threshold before writing.
    """
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    if not old_lines or len(old_lines) != len(new_lines):
        raise EditError(
            "fuzzy edits need the same number of lines in old and new"
        )
    lines = content.splitlines(keepends=True)
    start = _find_fuzzy(content, old)
    if start < 0:
        raise EditError("old text not found in file (even fuzzy)")
    pos = 0
    line_idx = 0
    for idx, line in enumerate(lines):
        if pos + len(line) > start:
            line_idx = idx
            break
        pos += len(line)
    if line_idx + len(old_lines) > len(lines):
        raise EditError("fuzzy match too close to the end of the file")
    matched = "".join(lines[line_idx : line_idx + len(old_lines)])
    if difflib.SequenceMatcher(None, matched, old).ratio() < FUZZY_THRESHOLD:
        raise EditError("fuzzy match rejected (similarity too low)")
    prefix = "".join(lines[:line_idx])
    suffix = "".join(lines[line_idx + len(old_lines) :])
    block = "".join(
        line if line.endswith("\n") else line + "\n" for line in new_lines
    )
    return prefix + block + suffix


def apply_patch(
    path: str,
    old: str,
    new: str,
    replace_all: bool = False,
    allow_syntax_errors: bool = False,
) -> EditResult:
    from eaccode.workspace import WorkspaceError, rewrite_path

    try:
        target = rewrite_path(path, _get_workspace())
    except WorkspaceError as exc:
        return EditResult(False, f"Error: {exc}")
    """Apply one patch; fuzzy-matches old text when exact lookup fails."""
    target = Path(path)
    if not target.exists():
        return EditResult(False, f"Error: no such file: {path}")
    try:
        content = target.read_text(encoding="utf-8")
    except OSError as exc:
        return EditResult(False, f"Error: cannot read {target}: {exc}")
    if not old:
        return EditResult(False, "Error: 'old' must not be empty")
    if old in content:
        if content.count(old) > 1 and not replace_all:
            return EditResult(
                False,
                f"Error: '{old[:60]}' is ambiguous ({content.count(old)} matches) "
                "- add more context or set replace_all",
            )
        new_content = content.replace(old, new) if replace_all else content.replace(old, new, 1)
    else:
        try:
            new_content = _apply_fuzzy(content, old, new)
        except EditError as exc:
            return EditResult(False, f"Error: {exc}")
    if not allow_syntax_errors:
        _session.backup(target)
        # Use the original file's suffix so syntax_check doesn't fire on
        # non-Python files (e.g. .txt, .md, .json). Was hardcoded ".py"
        # which made the check fire on every edit and reject non-Python
        # content. Plan G v6 — 08-18.
        with tempfile.NamedTemporaryFile(
            "w", suffix=target.suffix or ".py", delete=False, encoding="utf-8"
        ) as probe:
            probe.write(new_content)
            probe_name = probe.name
        try:
            issue = syntax_check(Path(probe_name))
        finally:
            os.unlink(probe_name)
        if issue:
            return EditResult(False, f"Error: {issue}")
    else:
        _session.backup(target)
    try:
        target.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        return EditResult(False, f"Error: cannot write {target}: {exc}")
    return EditResult(True, f"patched {target}")


def apply_multiple(edits: list[dict[str, Any]], allow_syntax_errors: bool = False) -> str:
    """Apply several patches; on failure, roll back the whole batch."""
    applied_count = 0
    try:
        for edit in edits:
            result = apply_patch(
                str(edit.get("path", "")),
                str(edit.get("old", "")),
                str(edit.get("new", "")),
                bool(edit.get("replace_all", False)),
                allow_syntax_errors=allow_syntax_errors,
            )
            if not result.ok:
                raise EditError(result.message)
            applied_count += 1
    except EditError as exc:
        for _ in range(applied_count):
            _session.undo()
        return f"Error: {exc} (all edits rolled back)"
    return f"applied {len(edits)} edits"


def edit_lines(
    path: str,
    action: str,
    line: int | None = None,
    end_line: int | None = None,
    text: str | None = None,
) -> EditResult:
    """Line-based edits: insert / replace / delete / append.

    Actions:
      insert  - insert ``text`` after line ``line`` (0 = at the top)
      replace - replace lines ``line..end_line`` (or just ``line``) with ``text``
      delete  - delete lines ``line..end_line`` (or just ``line``)
      append  - append ``text`` at the end of the file
    Backs up before writing (undoable) and syntax-checks .py files.
    """
    target = Path(path)
    if not target.exists():
        return EditResult(False, f"Error: no such file: {path}")
    try:
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError as exc:
        return EditResult(False, f"Error: cannot read {path}: {exc}")
    count = len(lines)
    action = action.lower()
    if action == "append":
        if text is None:
            return EditResult(False, "Error: append needs 'text'")
        new_lines = lines + [text if text.endswith("\n") else text + "\n"]
    elif action == "insert":
        if line is None or text is None:
            return EditResult(False, "Error: insert needs 'line' and 'text'")
        if line < 0 or line > count:
            return EditResult(
                False, f"Error: line {line} out of range (file has {count} lines)"
            )
        block = [t if t.endswith("\n") else t + "\n" for t in text.split("\n") if t != ""]
        new_lines = lines[:line] + block + lines[line:]
    elif action == "replace":
        if line is None or text is None:
            return EditResult(False, "Error: replace needs 'line' and 'text'")
        start = max(1, line)
        stop = min(end_line if end_line is not None else line, count)
        if start > count or stop < start:
            return EditResult(
                False, f"Error: line {line} out of range (file has {count} lines)"
            )
        block = [t if t.endswith("\n") else t + "\n" for t in text.split("\n") if t != ""]
        new_lines = lines[: start - 1] + block + lines[stop:]
    elif action == "delete":
        if line is None:
            return EditResult(False, "Error: delete needs 'line'")
        start = max(1, line)
        stop = min(end_line if end_line is not None else line, count)
        if start > count or stop < start:
            return EditResult(
                False, f"Error: line {line} out of range (file has {count} lines)"
            )
        new_lines = lines[: start - 1] + lines[stop:]
    else:
        return EditResult(
            False, f"Error: unknown action '{action}' (use insert/replace/delete/append)"
        )
    new_content = "".join(new_lines)
    if not new_content.endswith("\n") and new_content:
        new_content += "\n"
    _session.backup(target)
    # Use original file's suffix so syntax_check only fires on .py files.
    # Was hardcoded ".py" which made the check fire on every edit
    # (e.g. .txt, .md, .json files). Plan G v6 — 08-18.
    with tempfile.NamedTemporaryFile(
        "w", suffix=target.suffix or ".py", delete=False, encoding="utf-8"
    ) as probe:
        probe.write(new_content)
        probe_name = probe.name
    try:
        issue = syntax_check(Path(probe_name))
    finally:
        with __import__("contextlib").suppress(OSError):
            os.unlink(probe_name)
    if issue:
        return EditResult(False, f"Error: {issue}")
    try:
        target.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        return EditResult(False, f"Error: cannot write {path}: {exc}")
    return EditResult(True, f"{action}: {path} ({count} -> {len(new_lines)} lines)")


def _tool_file_edit(
    path: str,
    action: str,
    line: int | None = None,
    end_line: int | None = None,
    text: str | None = None,
) -> str:
    result = edit_lines(path, action, line, end_line, text)
    return result.message


def _tool_patch_file(path: str, old: str, new: str) -> str:
    result = apply_patch(path, old, new)
    return result.message


def _tool_patch_multiple(edits: list[dict[str, Any]]) -> str:
    return apply_multiple(edits)


def _tool_undo_edit() -> str:
    return _session.undo()


def make_editing_tools() -> list[Tool]:
    """Agent tools for diff editing (D2)."""
    edit_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Path to the file to edit. Sensitive paths "
                    "(.ssh/, .env, config.yaml) trigger permission "
                    "review."
                ),
            },
            "old": {
                "type": "string",
                "description": (
                    "Exact text to find. Falls back to fuzzy match if "
                    "no exact match (Python files only)."
                ),
            },
            "new": {
                "type": "string",
                "description": "Replacement text (must match old line-count for fuzzy).",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace every occurrence (default: false; one match).",
            },
        },
        "required": ["path", "old", "new"],
    }
    return [
        Tool(
            "file_edit",
            "Line-based edit: insert/replace/delete/append lines in a file. "
            "Returns '<action>: <path> (N -> M lines)' on success, "
            "'Error: line N out of range ...' on bad range, 'Error: "
            "unknown action ...' on bad action name. Python files are "
            "syntax-checked. Always undoable via undo_edit (max 20 deep).",
            _tool_file_edit,
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path. Parent dirs auto-created.",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["insert", "replace", "delete", "append"],
                        "description": "Type of line edit.",
                    },
                    "line": {
                        "type": "integer",
                        "description": "1-based line number (insert/replace/delete).",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": (
                            "Inclusive end line for range operations "
                            "(replace/delete). Optional."
                        ),
                    },
                    "text": {
                        "type": "string",
                        "description": (
                            "Content to insert / replace with. Use \n in "
                            "JSON-strings for multi-line content."
                        ),
                    },
                },
                "required": ["path", "action"],
            },
            mutates=True,
        ),
        Tool(
            "patch_file",
            "Replace old text with new text in a file (exact or fuzzy match). "
            "Python files syntax-check before write. Returns 'patched <path>' "
            "on success, 'Error: <...> is ambiguous (N matches) - add more "
            "context or set replace_all' on ambiguity, or "
            "'Error: old text not found in file (even fuzzy)' when no match.",
            _tool_patch_file,
            edit_schema,
            mutates=True,
        ),
        Tool(
            "patch_multiple",
            "Apply several edits across files atomically; the whole batch is "
            "rolled back (via undo_edit stack) when one edit fails. Returns "
            "'applied N edits' or 'Error: <reason> (all edits rolled back)'.",
            _tool_patch_multiple,
            {
                "type": "object",
                "properties": {
                    "edits": {
                        "type": "array",
                        "description": "List of patch_file-style edits (atomic).",
                        "items": edit_schema,
                    },
                },
                "required": ["edits"],
            },
            mutates=True,
        ),
        Tool(
            "undo_edit",
            "Roll back the most recent edit (backup stack, max 20). Returns "
            "'undone: <path>' on success, 'Error: nothing to undo' when the "
            "stack is empty. Mutating but not edit-creating on its own.",
            _tool_undo_edit,
            {"type": "object", "properties": {}, "required": []},
            mutates=True,
        ),
    ]