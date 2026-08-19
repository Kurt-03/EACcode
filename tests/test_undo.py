"""Tests for undo + diff-preview (Plan I P1.7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaccode import undo as undo_mod
from eaccode.undo import (
    UndoSnapshot,
    clear_snapshots,
    discard_snapshot,
    format_diff_preview,
    list_snapshots,
    restore_snapshot,
    save_snapshot,
)


@pytest.fixture
def session_id(monkeypatch):
    """Patch undo_dir to use tmp_path so we don't pollute the real filesystem."""
    sid = "test-session-1"

    def fake_dir(s):
        return Path(f"/tmp/eaccode-undo/{s}") if monkeypatch else Path(f"/tmp/eaccode-undo/{s}")

    monkeypatch.setattr(undo_mod, "undo_dir", lambda s: Path(f"/tmp/eaccode-undo/{s}"))
    return sid


class TestDiffPreview:
    def test_no_changes(self) -> None:
        assert format_diff_preview("hello", "hello") == "(no changes)"

    def test_addition(self) -> None:
        out = format_diff_preview("", "new line", "x.py")
        assert "+new line" in out
        assert "a/x.py" in out
        assert "b/x.py" in out

    def test_deletion(self) -> None:
        out = format_diff_preview("old line", "", "x.py")
        assert "-old line" in out

    def test_modification(self) -> None:
        out = format_diff_preview("old", "new", "x.py")
        assert "-old" in out
        assert "+new" in out


class TestSnapshotLifecycle:
    def test_save_and_list(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(undo_mod, "undo_dir", lambda s: tmp_path / s)
        snap = save_snapshot("s1", "/repo/foo.py", "old content")
        snaps = list_snapshots("s1")
        assert len(snaps) == 1
        assert snaps[0].path == "/repo/foo.py"
        assert snaps[0].old_content == "old content"
        assert snap.timestamp

    def test_save_new_file(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(undo_mod, "undo_dir", lambda s: tmp_path / s)
        snap = save_snapshot("s1", "/repo/new.py", None)
        assert snap.old_content is None

    def test_list_filter_by_path(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(undo_mod, "undo_dir", lambda s: tmp_path / s)
        save_snapshot("s1", "/repo/a.py", "a")
        save_snapshot("s1", "/repo/b.py", "b")
        snaps = list_snapshots("s1", path="/repo/a.py")
        assert len(snaps) == 1
        assert snaps[0].path == "/repo/a.py"

    def test_restore_modification(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(undo_mod, "undo_dir", lambda s: tmp_path / s)
        target = tmp_path / "foo.py"
        target.write_text("new content", encoding="utf-8")
        snap = save_snapshot("s1", str(target), "old content")
        assert restore_snapshot(snap) is True
        assert target.read_text(encoding="utf-8") == "old content"

    def test_restore_new_file_deletes(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(undo_mod, "undo_dir", lambda s: tmp_path / s)
        target = tmp_path / "new.py"
        target.write_text("content", encoding="utf-8")
        snap = save_snapshot("s1", str(target), None)
        assert restore_snapshot(snap) is True
        assert not target.exists()

    def test_discard_snapshot(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(undo_mod, "undo_dir", lambda s: tmp_path / s)
        snap = save_snapshot("s1", "/x.py", "old")
        assert discard_snapshot(snap) is True
        assert list_snapshots("s1") == []

    def test_clear_all(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(undo_mod, "undo_dir", lambda s: tmp_path / s)
        save_snapshot("s1", "/a.py", "a")
        save_snapshot("s1", "/b.py", "b")
        assert clear_snapshots("s1") == 2
        assert list_snapshots("s1") == []