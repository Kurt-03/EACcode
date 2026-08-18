"""Tests for live_transcript (Phase G.7, Plan G v5)."""

from __future__ import annotations

import re

import pytest

from eaccode import live_transcript as lt
from eaccode.live_transcript import LiveTranscriptWriter


@pytest.fixture
def writer(tmp_path, monkeypatch) -> LiveTranscriptWriter:
    """Create a writer rooted at tmp_path."""
    monkeypatch.setattr(lt, "live_transcript_root", lambda: tmp_path)
    return LiveTranscriptWriter(delegation_id="d1", tool_name="test_tool")


class TestOneLine:
    def test_flattens_newlines(self) -> None:
        out = lt._one_line("hello\nworld\nfoo")
        # Newlines become literal \n
        assert "\\n" in out
        # No raw newlines in the output
        assert "\n" not in out

    def test_collapses_whitespace(self) -> None:
        assert lt._one_line("a   b\tc") == "a b c"

    def test_caps_length(self) -> None:
        out = lt._one_line("x" * 1000, limit=50)
        assert len(out) <= 50


class TestRedact:
    def test_redacts_anthropic_key(self) -> None:
        s = "Bearer sk-ant-abcdef1234567890xyzXYZ1234"
        out = lt.redact(s)
        assert "sk-ant-***" in out
        assert "abcdef" not in out

    def test_redacts_github_pat(self) -> None:
        s = "token=ghp_abcdefghijklmnopqrstuvwx"
        out = lt.redact(s)
        assert "ghp_***" in out

    def test_leaves_clean_text(self) -> None:
        s = "this is a normal message"
        assert lt.redact(s) == s


class TestWriter:
    def test_log_writes_line(self, writer) -> None:
        writer.log("hello world")
        assert writer.path.exists()
        content = writer.path.read_text(encoding="utf-8")
        assert "hello world" in content
        assert "[test_tool]" in content

    def test_log_after_close_is_noop(self, writer) -> None:
        # First write something so the file exists
        writer.log("before close")
        writer.close()
        # Now log after close: noop
        writer.log("after close")
        content = writer.path.read_text(encoding="utf-8")
        assert "after close" not in content
        assert "before close" in content

    def test_log_appends(self, writer) -> None:
        writer.log("first")
        writer.log("second")
        content = writer.path.read_text(encoding="utf-8")
        lines = [ln for ln in content.splitlines() if ln.strip()]
        assert len(lines) == 2
        assert "first" in lines[0]
        assert "second" in lines[1]

    def test_log_redacts_secrets(self, writer) -> None:
        writer.log("token sk-ant-abcdefghijklmnopqrstuvwxyzAB")
        content = writer.path.read_text(encoding="utf-8")
        assert "sk-ant-***" in content

    def test_log_with_extra_fields(self, writer) -> None:
        writer.log("event", tool="x", duration="1.2s")
        content = writer.path.read_text(encoding="utf-8")
        assert "tool=x" in content
        assert "duration=1.2s" in content


class TestNewId:
    def test_format(self) -> None:
        delegation_id = lt.new_live_delegation_id()
        assert delegation_id.startswith("sub-")
        assert len(delegation_id.split("-")) == 3


class TestWrapProgressCallback:
    def test_logs_to_writer(self, writer) -> None:
        captured: list[str] = []

        def inner_cb(line: str) -> None:
            captured.append(line)

        wrapped = lt.wrap_progress_callback(inner_cb, writer)
        wrapped("first step done")
        wrapped("second step done")

        assert "first step done" in writer.path.read_text(encoding="utf-8")
        assert captured == ["first step done", "second step done"]

    def test_continues_when_inner_raises(self, writer) -> None:
        def bad_cb(line: str) -> None:
            raise RuntimeError("boom")

        wrapped = lt.wrap_progress_callback(bad_cb, writer)
        wrapped("still works")
        assert "still works" in writer.path.read_text(encoding="utf-8")


class TestPrune:
    def test_prunes_stale_dirs(self, tmp_path, monkeypatch) -> None:
        import os, time

        monkeypatch.setattr(lt, "live_transcript_root", lambda: tmp_path)
        fresh = tmp_path / "fresh"
        fresh.mkdir()
        stale = tmp_path / "stale"
        stale.mkdir()
        # Make stale look old
        old_time = time.time() - (10 * 86400)
        os.utime(stale, (old_time, old_time))

        removed = lt.prune_stale_live_dirs(max_age_days=3)
        assert removed == 1
        assert (tmp_path / "fresh").exists()
        assert not (tmp_path / "stale").exists()


class TestUpdateManifest:
    def test_writes_manifest(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(lt, "live_transcript_root", lambda: tmp_path)
        (tmp_path / "d1").mkdir()
        lt.update_manifest_status("d1", "running")
        path = tmp_path / "d1" / "manifest.json"
        assert path.exists()
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["status"] == "running"
