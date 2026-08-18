"""Tests for approvals_store (Plan H.minimal v4, Tag 3)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaccode import approvals_store as aps
from eaccode.workspace import PathRule


@pytest.fixture
def store(tmp_path: Path) -> aps.ApprovalsStore:
    return aps.ApprovalsStore(path=tmp_path / "approvals.json")


class TestLoad:
    def test_load_missing_returns_empty(self, store) -> None:
        assert store.load() == []

    def test_load_corrupt_returns_empty(self, store) -> None:
        store.path.write_text("not json", encoding="utf-8")
        assert store.load() == []

    def test_load_non_list_returns_empty(self, store) -> None:
        store.path.write_text("{}", encoding="utf-8")
        assert store.load() == []

    def test_load_valid(self, store) -> None:
        store.path.write_text(
            json.dumps([{"raw": "C:/foo", "scope": "always", "kind": "allow"}]),
            encoding="utf-8",
        )
        rules = store.load()
        assert len(rules) == 1
        assert rules[0].raw == "C:/foo"

    def test_load_invalid_entry_skipped(self, store) -> None:
        store.path.write_text(
            json.dumps([
                {"raw": "good", "scope": "always", "kind": "allow"},
                {"raw": "bad", "scope": "permanent", "kind": "allow"},  # bad scope
            ]),
            encoding="utf-8",
        )
        rules = store.load()
        assert len(rules) == 1


class TestSave:
    def test_save_creates_parent(self, tmp_path) -> None:
        store = aps.ApprovalsStore(path=tmp_path / "deep" / "approvals.json")
        store.save([PathRule(raw="x", scope="always", kind="allow")])
        assert store.path.exists()

    def test_save_writes_only_always_scoped(self, store) -> None:
        rules = [
            PathRule(raw="a", scope="always", kind="allow"),
            PathRule(raw="b", scope="session", kind="allow"),
            PathRule(raw="c", scope="once", kind="deny"),
        ]
        store.save(rules)
        loaded = store.load()
        assert len(loaded) == 1
        assert loaded[0].raw == "a"

    def test_save_round_trip(self, store) -> None:
        original = [
            PathRule(raw="foo", scope="always", kind="allow"),
            PathRule(raw="bar", scope="always", kind="deny"),
        ]
        store.save(original)
        loaded = store.load()
        assert [(r.raw, r.scope, r.kind) for r in loaded] == [
            (r.raw, r.scope, r.kind) for r in original
        ]

    def test_clear(self, store) -> None:
        store.save([PathRule(raw="x", scope="always", kind="allow")])
        store.clear()
        assert not store.path.exists()


class TestDefaultPath:
    def test_default_path_includes_eaccode(self) -> None:
        p = aps.default_store_path()
        assert "eaccode" in str(p)
        assert p.name == "approvals.json"