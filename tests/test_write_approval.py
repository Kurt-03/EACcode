"""Tests for write_approval stage-approval (Plan H.minimal v4 Stufe 2, Hermes analog)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaccode import write_approval as wa
from eaccode.write_approval import (
    PendingWrite,
    STAGED_SUBSYSTEMS,
    clear_pending,
    discard_pending,
    get_pending,
    list_pending,
    pending_count,
    pending_dir,
    stage_write,
)


@pytest.fixture
def sandbox_pending(monkeypatch, tmp_path):
    """Point pending dirs at a tmp tree (one tmp dir per subsystem)."""
    subs_dirs = {}
    for sub in STAGED_SUBSYSTEMS:
        d = tmp_path / sub
        d.mkdir(parents=True, exist_ok=True)
        subs_dirs[sub] = d

    def fake_pending_dir(subsystem: str):
        return subs_dirs[subsystem]

    monkeypatch.setattr(wa, "pending_dir", fake_pending_dir)
    yield tmp_path


class TestStage:
    def test_returns_pending_write(self, sandbox_pending) -> None:
        pw = stage_write("memory", {"action": "add", "content": "x"}, summary="test")
        assert isinstance(pw, PendingWrite)
        assert pw.id
        assert pw.subsystem == "memory"

    def test_persists_to_disk(self, sandbox_pending) -> None:
        pw = stage_write("memory", {"action": "add"}, summary="x")
        path = sandbox_pending / "memory" / f"{pw.id}.json"
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["id"] == pw.id

    def test_unknown_subsystem_raises(self, sandbox_pending) -> None:
        with pytest.raises(ValueError):
            stage_write("foo", {}, summary="x")

    def test_payload_kept(self, sandbox_pending) -> None:
        pw = stage_write(
            "skills",
            {"action": "create", "name": "foo", "content": "bar"},
            summary="skill foo",
        )
        assert pw.payload["name"] == "foo"


class TestListPending:
    def test_empty(self, sandbox_pending) -> None:
        assert list_pending("memory") == []

    def test_returns_all(self, sandbox_pending) -> None:
        for i in range(3):
            stage_write("memory", {"action": "add", "i": i}, summary=f"s{i}")
        items = list_pending("memory")
        assert len(items) == 3

    def test_newest_first(self, sandbox_pending) -> None:
        a = stage_write("memory", {"a": 1}, summary="a")
        b = stage_write("memory", {"b": 2}, summary="b")
        items = list_pending("memory")
        assert items[0].id == b.id
        assert items[1].id == a.id


class TestGetPending:
    def test_existing(self, sandbox_pending) -> None:
        pw = stage_write("memory", {"x": 1}, summary="x")
        got = get_pending("memory", pw.id)
        assert got is not None
        assert got.id == pw.id

    def test_missing(self, sandbox_pending) -> None:
        assert get_pending("memory", "missing-id") is None


class TestDiscard:
    def test_removes(self, sandbox_pending) -> None:
        pw = stage_write("memory", {"x": 1}, summary="x")
        assert discard_pending("memory", pw.id) is True
        assert not (sandbox_pending / "memory" / f"{pw.id}.json").exists()

    def test_missing_returns_false(self, sandbox_pending) -> None:
        assert discard_pending("memory", "missing-id") is False


class TestCount:
    def test_zero(self, sandbox_pending) -> None:
        assert pending_count("memory") == 0

    def test_three(self, sandbox_pending) -> None:
        for i in range(3):
            stage_write("memory", {"i": i}, summary=f"s{i}")
        assert pending_count("memory") == 3


class TestClear:
    def test_clear_removes_all(self, sandbox_pending) -> None:
        for i in range(3):
            stage_write("memory", {"i": i}, summary=f"s{i}")
        removed = clear_pending("memory")
        assert removed == 3
        assert pending_count("memory") == 0


class TestSubsystemValidation:
    def test_unknown_subsystem(self, sandbox_pending) -> None:
        with pytest.raises(ValueError):
            list_pending("bogus")

    def test_subsystem_constants(self) -> None:
        assert "memory" in STAGED_SUBSYSTEMS
        assert "skills" in STAGED_SUBSYSTEMS