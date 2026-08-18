"""Tests for blocked.py (Phase C.8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaccode.blocked import BlockedPatternsStore


@pytest.fixture
def store(tmp_path: Path) -> BlockedPatternsStore:
    return BlockedPatternsStore(tmp_path / "blocked.json")


class TestAddRemove:
    def test_add_returns_id(self, store: BlockedPatternsStore) -> None:
        entry_id = store.add("rm-rf-~", "destructive", "run_command")
        assert isinstance(entry_id, str)
        assert len(entry_id) >= 4

    def test_list_after_add(self, store: BlockedPatternsStore) -> None:
        store.add("p1", "r1")
        store.add("p2", "r2")
        listed = store.list()
        assert len(listed) == 2
        patterns = {e["pattern"] for e in listed}
        assert patterns == {"p1", "p2"}

    def test_remove(self, store: BlockedPatternsStore) -> None:
        entry_id = store.add("p1", "r1")
        assert store.remove(entry_id) is True
        assert len(store.list()) == 0

    def test_remove_unknown(self, store: BlockedPatternsStore) -> None:
        assert store.remove("nonexistent") is False


class TestPersistence:
    def test_persists_to_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "blocked.json"
        s1 = BlockedPatternsStore(path)
        s1.add("p1", "r1", "run_command")

        # New instance should read the same data
        s2 = BlockedPatternsStore(path)
        assert len(s2.list()) == 1
        assert s2.list()[0]["pattern"] == "p1"

    def test_handles_missing_file(self, tmp_path: Path) -> None:
        s = BlockedPatternsStore(tmp_path / "missing.json")
        assert s.list() == []

    def test_handles_corrupted_file(self, tmp_path: Path) -> None:
        path = tmp_path / "blocked.json"
        path.write_text("not valid json{", encoding="utf-8")
        s = BlockedPatternsStore(path)
        assert s.list() == []  # graceful fallback


class TestMatches:
    def test_returns_matching_entry(self, store: BlockedPatternsStore) -> None:
        store.add(r"chmod\s+777", "world-writable", "run_command")
        m = store.matches("run_command {\"command\": \"chmod 777 /tmp\"}")
        assert m is not None
        assert m["pattern"] == r"chmod\s+777"

    def test_no_match(self, store: BlockedPatternsStore) -> None:
        store.add("dangerous", "test")
        assert store.matches("safe command") is None

    def test_case_insensitive(self, store: BlockedPatternsStore) -> None:
        store.add("dangerous", "test-reason")
        assert store.matches("DANGEROUS command") is not None

    def test_invalid_pattern_ignored(self, store: BlockedPatternsStore) -> None:
        store.add("[invalid(", "bad regex")  # invalid regex
        # Should not crash
        assert store.matches("anything") is None

    def test_first_match_wins(self, store: BlockedPatternsStore) -> None:
        store.add("alpha", "first")
        store.add("beta", "second")
        m = store.matches("alpha beta gamma")
        assert m["reason"] == "first"
