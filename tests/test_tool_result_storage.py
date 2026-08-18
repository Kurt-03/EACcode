"""Tests for tool_result_storage (Phase G.3, Plan G v5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import tool_result_storage as trs


@pytest.fixture
def storage_root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(trs, "_storage_dir", lambda: tmp_path)
    return tmp_path


class TestPersistToolResult:
    def test_empty_body_returns_empty_meta(self, storage_root) -> None:
        meta = trs.persist_tool_result("read_file", "c1", "")
        assert meta["path"] is None
        assert meta["size_chars"] == 0
        assert meta["hash"] == ""

    def test_writes_file(self, storage_root) -> None:
        meta = trs.persist_tool_result("read_file", "c1", "hello world")
        assert meta["path"] is not None
        path = Path(meta["path"])
        assert path.exists()
        assert path.read_text(encoding="utf-8") == "hello world"
        assert meta["size_chars"] == 11

    def test_preview_truncated(self, storage_root) -> None:
        body = "x" * (trs.MAX_PREVIEW_CHARS + 200)
        meta = trs.persist_tool_result("read_file", "c1", body)
        # Preview ends with ellipsis
        assert meta["preview"].endswith("…")
        # Full body still on disk
        assert Path(meta["path"]).read_text(encoding="utf-8") == body


class TestMaybePersist:
    def test_small_body_passes_through(self, storage_root) -> None:
        body, meta = trs.maybe_persist_tool_result(
            "read_file", "c1", "small body", threshold_chars=100
        )
        assert body == "small body"
        assert meta is None

    def test_large_body_persists(self, storage_root) -> None:
        body, meta = trs.maybe_persist_tool_result(
            "read_file", "c1", "x" * 200, threshold_chars=100
        )
        from eaccode.tool_result_storage import PERSISTED_OUTPUT_TAG
        assert PERSISTED_OUTPUT_TAG in body
        assert meta is not None

    def test_preview_includes_path(self, storage_root) -> None:
        body, meta = trs.maybe_persist_tool_result(
            "read_file", "c1", "x" * 200, threshold_chars=100
        )
        assert meta is not None
        assert meta["path"] in body


class TestEnforceTurnBudget:
    def test_no_op_when_under_budget(self, storage_root) -> None:
        results = [
            {"tool_call_id": "c1", "tool_name": "read_file", "content": "short"},
            {"tool_call_id": "c2", "tool_name": "list_files", "content": "tiny"},
        ]
        out = trs.enforce_turn_budget(results, max_chars=10_000)
        assert out == results

    def test_spills_largest_when_over_budget(self, storage_root) -> None:
        big = "x" * 8000
        medium = "y" * 4000
        small = "z" * 1000
        results = [
            {"tool_call_id": "c1", "tool_name": "read_file", "content": big},
            {"tool_call_id": "c2", "tool_name": "read_file", "content": medium},
            {"tool_call_id": "c3", "tool_name": "read_file", "content": small},
        ]
        # Set a budget that forces spilling
        out = trs.enforce_turn_budget(results, max_chars=10_000)
        # Total must fit under budget now
        total = sum(len(str(r.get("content", ""))) for r in out)
        # The small one stays in-context; medium/big are spilled
        small_out = next(r for r in out if r["tool_call_id"] == "c3")
        assert small_out["content"] == small
        big_out = next(r for r in out if r["tool_call_id"] == "c1")
        from eaccode.tool_result_storage import PERSISTED_OUTPUT_TAG
        assert PERSISTED_OUTPUT_TAG in big_out["content"]

    def test_skips_already_persisted(self, storage_root) -> None:
        """Already-persisted results are recognised by the tag and skipped."""
        from eaccode.tool_result_storage import (
            PERSISTED_OUTPUT_TAG,
            PERSISTED_OUTPUT_CLOSING_TAG,
        )
        original = (
            f"{PERSISTED_OUTPUT_TAG}some preview{PERSISTED_OUTPUT_CLOSING_TAG}"
        )
        results = [
            {
                "tool_call_id": "c1",
                "tool_name": "read_file",
                "content": original,
            }
        ]
        # Budget big enough that no further spilling happens; the
        # already-persisted entry should be left untouched.
        out = trs.enforce_turn_budget(results, max_chars=10_000)
        assert out[0]["content"] == original


class TestFilenameSafety:
    def test_special_chars_sanitised(self) -> None:
        name = trs._safe_filename("../../../etc/passwd")
        assert "/" not in name
        assert ".." not in name

    def test_empty_id_uses_uuid(self) -> None:
        name = trs._safe_filename("")
        assert name  # non-empty

    def test_long_id_truncated(self) -> None:
        name = trs._safe_filename("x" * 500)
        assert len(name) <= trs._MAX_FILENAME_STEM
