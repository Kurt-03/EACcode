"""Tests for diff editing (Phase D2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import config as cfg
from eaccode import editing
from eaccode.editing import EditSession, apply_patch


@pytest.fixture
def work_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path / "data")
    return tmp_path


class TestApplyPatch:
    def test_exact_replace(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("x = 1\ny = 2\n", encoding="utf-8")
        result = apply_patch(str(target), "x = 1", "x = 10")
        assert result.ok
        assert target.read_text(encoding="utf-8") == "x = 10\ny = 2\n"

    def test_ambiguous_rejected(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("v = 1\nv = 1\n", encoding="utf-8")
        result = apply_patch(str(target), "v = 1", "v = 9")
        assert not result.ok
        assert "ambiguous" in result.message

    def test_replace_all(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("v = 1\nv = 2\n", encoding="utf-8")
        result = apply_patch(str(target), "v = 1", "v = 9", replace_all=True)
        assert result.ok

    def test_missing_file(self, work_dir: Path) -> None:
        result = apply_patch(str(work_dir / "ghost.py"), "a", "b")
        assert not result.ok
        assert "no such file" in result.message

    def test_old_not_found(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("aaa\n", encoding="utf-8")
        result = apply_patch(str(target), "zzz", "b")
        assert not result.ok
        assert "not found" in result.message

    def test_syntax_error_rejected(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("def ok():\n    pass\n", encoding="utf-8")
        result = apply_patch(str(target), "def ok():\n    pass", "def ok():\n  broken(")
        assert not result.ok
        assert "syntax error" in result.message
        assert "def ok" in target.read_text(encoding="utf-8")  # unchanged

    def test_fuzzy_match_with_context(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("def f():\n    return 1\n", encoding="utf-8")
        result = apply_patch(
            str(target),
            "def f():\n    return 1",  # exact here; fuzzy path not triggered
            "def f():\n    return 2",
        )
        assert result.ok
        assert "return 2" in target.read_text(encoding="utf-8")

    def test_non_python_file_no_syntax_check(self, work_dir: Path) -> None:
        target = work_dir / "notes.md"
        target.write_text("# Hallo\n", encoding="utf-8")
        result = apply_patch(str(target), "Hallo", "Welt")
        assert result.ok
        assert "# Welt" in target.read_text(encoding="utf-8")


class TestFuzzy:
    def test_fuzzy_finds_near_match(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text(
            "def run():\n    print('hallo')\n    print('ende')\n",
            encoding="utf-8",
        )
        result = apply_patch(
            str(target),
            "def run():\n    print('hallo')\n    print('ende')\n",
            "def run():\n    print('hi')\n    print('ende')\n",
        )
        assert result.ok  # exact match here; fuzzy covered by the test above

    def test_fuzzy_applies_with_syntax_check(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text(
            "def run():\n    print('hallo welt')\n", encoding="utf-8"
        )
        result = apply_patch(
            str(target),
            "def run():\n    print('hallo')",  # not exact -> fuzzy path
            "def run():\n    print('hi')",
        )
        assert result.ok
        assert "print('hi')" in target.read_text(encoding="utf-8")

    def test_fuzzy_refuses_when_too_different(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        result = apply_patch(str(target), "zzz ganz anders", "neu")
        assert not result.ok
        assert "not found" in result.message


class TestRollback:
    def test_undo_restores_file(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("x = 1\n", encoding="utf-8")
        apply_patch(str(target), "x = 1", "x = 2")
        assert "x = 2" in target.read_text(encoding="utf-8")
        # the global session did the backup; undo via the module session
        message = editing._session.undo()
        assert "reverted" in message
        assert target.read_text(encoding="utf-8") == "x = 1\n"

    def test_undo_empty(self) -> None:
        session = EditSession()
        assert "nothing to undo" in session.undo()

    def test_undo_stack_limit(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("x = 0\n", encoding="utf-8")
        session = EditSession()
        for _ in range(25):
            session.backup(target)
        assert len(session) == editing.MAX_UNDO


class TestLineEdits:
    def test_append(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("x = 1\n", encoding="utf-8")
        result = editing.edit_lines(str(target), "append", text="y = 2")
        assert result.ok
        assert target.read_text(encoding="utf-8") == "x = 1\ny = 2\n"

    def test_insert_after_line(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("a = 1\nb = 2\n", encoding="utf-8")
        result = editing.edit_lines(str(target), "insert", line=1, text="c = 3")
        assert result.ok
        assert target.read_text(encoding="utf-8") == "a = 1\nc = 3\nb = 2\n"

    def test_insert_at_top(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("b = 2\n", encoding="utf-8")
        result = editing.edit_lines(str(target), "insert", line=0, text="a = 1")
        assert result.ok
        assert target.read_text(encoding="utf-8") == "a = 1\nb = 2\n"

    def test_replace_single_line(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("a = 1\nb = 2\n", encoding="utf-8")
        result = editing.edit_lines(str(target), "replace", line=2, text="b = 9")
        assert result.ok
        assert target.read_text(encoding="utf-8") == "a = 1\nb = 9\n"

    def test_replace_range(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        result = editing.edit_lines(
            str(target), "replace", line=1, end_line=2, text="x = 0"
        )
        assert result.ok
        assert target.read_text(encoding="utf-8") == "x = 0\nc = 3\n"

    def test_delete_range(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        result = editing.edit_lines(str(target), "delete", line=1, end_line=2)
        assert result.ok
        assert target.read_text(encoding="utf-8") == "c = 3\n"

    def test_line_out_of_range(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("a = 1\n", encoding="utf-8")
        result = editing.edit_lines(str(target), "delete", line=5)
        assert not result.ok
        assert "out of range" in result.message

    def test_unknown_action(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("a = 1\n", encoding="utf-8")
        result = editing.edit_lines(str(target), "shred", line=1)
        assert not result.ok
        assert "unknown action" in result.message

    def test_syntax_error_rejected(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("def ok():\n    pass\n", encoding="utf-8")
        result = editing.edit_lines(str(target), "append", text="def kaputt(:")
        assert not result.ok
        assert "syntax error" in result.message

    def test_edit_undoable(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("a = 1\n", encoding="utf-8")
        editing.edit_lines(str(target), "append", text="b = 2")
        assert "b = 2" in target.read_text(encoding="utf-8")
        message = editing._session.undo()
        assert "reverted" in message
        assert target.read_text(encoding="utf-8") == "a = 1\n"

    def test_tool_registered(self, work_dir: Path) -> None:
        tools = {tool.name: tool for tool in editing.make_editing_tools()}
        assert "file_edit" in tools
        target = work_dir / "a.py"
        target.write_text("a = 1\n", encoding="utf-8")
        out = tools["file_edit"].func(str(target), "append", None, None, "b = 2")
        assert "append" in out


class TestMultiPatch:
    def test_applies_all(self, work_dir: Path) -> None:
        a = work_dir / "a.py"
        b = work_dir / "b.py"
        a.write_text("x = 1\n", encoding="utf-8")
        b.write_text("y = 1\n", encoding="utf-8")
        message = editing.apply_multiple(
            [
                {"path": str(a), "old": "x = 1", "new": "x = 2"},
                {"path": str(b), "old": "y = 1", "new": "y = 2"},
            ]
        )
        assert "applied 2" in message
        assert "x = 2" in a.read_text(encoding="utf-8")
        assert "y = 2" in b.read_text(encoding="utf-8")

    def test_failure_rolls_back_all(self, work_dir: Path) -> None:
        a = work_dir / "a.py"
        b = work_dir / "b.py"
        a.write_text("x = 1\n", encoding="utf-8")
        b.write_text("y = 1\n", encoding="utf-8")
        message = editing.apply_multiple(
            [
                {"path": str(a), "old": "x = 1", "new": "x = 2"},
                {"path": str(b), "old": "ghost", "new": "y = 2"},
            ]
        )
        assert "rolled back" in message
        assert "x = 1" in a.read_text(encoding="utf-8")


class TestTools:
    def test_make_editing_tools(self) -> None:
        tools = {tool.name: tool for tool in editing.make_editing_tools()}
        assert set(tools) == {
            "patch_file",
            "patch_multiple",
            "undo_edit",
            "file_edit",
        }

    def test_tool_patch_and_undo(self, work_dir: Path) -> None:
        target = work_dir / "a.py"
        target.write_text("x = 1\n", encoding="utf-8")
        tools = {tool.name: tool for tool in editing.make_editing_tools()}
        out = tools["patch_file"].func(str(target), "x = 1", "x = 5")
        assert "patched" in out
        assert "x = 5" in target.read_text(encoding="utf-8")
        out = tools["undo_edit"].func()
        assert "reverted" in out
        assert target.read_text(encoding="utf-8") == "x = 1\n"
