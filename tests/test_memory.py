"""Tests for the persistent memory layer (Phase A6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import config as cfg
from eaccode import memory


@pytest.fixture
def tmp_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    return tmp_path


class TestMemory:
    def test_add_creates_file(self, tmp_memory: Path) -> None:
        assert memory.add_entry(memory.memory_path(), "Lieblingsfarbe ist grün") == "ok"
        content = memory.read_file(memory.memory_path())
        assert content == "- Lieblingsfarbe ist grün"

    def test_add_appends(self, tmp_memory: Path) -> None:
        memory.add_entry(memory.memory_path(), "erster Fakt")
        memory.add_entry(memory.memory_path(), "zweiter Fakt")
        content = memory.read_file(memory.memory_path())
        assert content == "- erster Fakt\n- zweiter Fakt"

    def test_add_rejects_empty(self, tmp_memory: Path) -> None:
        assert "Error" in memory.add_entry(memory.memory_path(), "   ")

    def test_remove_entry(self, tmp_memory: Path) -> None:
        memory.add_entry(memory.memory_path(), "alter Fakt")
        memory.add_entry(memory.memory_path(), "neuer Fakt")
        assert memory.remove_entry(memory.memory_path(), "alter") == "ok"
        content = memory.read_file(memory.memory_path())
        assert content == "- neuer Fakt"

    def test_remove_missing_substring_errors(self, tmp_memory: Path) -> None:
        memory.add_entry(memory.memory_path(), "einziger Fakt")
        assert "Error" in memory.remove_entry(memory.memory_path(), "gibtsnicht")

    def test_remove_empty_memory_errors(self, tmp_memory: Path) -> None:
        assert "Error" in memory.remove_entry(memory.memory_path(), "x")

    def test_user_file_separate(self, tmp_memory: Path) -> None:
        memory.add_entry(memory.user_path(), "spricht Deutsch")
        assert memory.user_path().exists()
        assert memory.read_file(memory.memory_path()) == ""


class TestInjection:
    def test_empty_memory_yields_nothing(self, tmp_memory: Path) -> None:
        assert memory.injection_text() == ""

    def test_injection_contains_both_sections(self, tmp_memory: Path) -> None:
        memory.add_entry(memory.memory_path(), "Agent-Fakt")
        memory.add_entry(memory.user_path(), "User-Fakt")
        text = memory.injection_text()
        assert "## Agent Memory" in text
        assert "- Agent-Fakt" in text
        assert "## About the User" in text
        assert "- User-Fakt" in text

    def test_injection_skips_empty_user(self, tmp_memory: Path) -> None:
        memory.add_entry(memory.memory_path(), "nur Agent")
        text = memory.injection_text()
        assert "## Agent Memory" in text
        assert "About the User" not in text
