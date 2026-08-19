"""Tests for todo tool (Plan I P1.5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eaccode import todo as todo_mod
from eaccode.todo import (
    TODO_STATUSES,
    TodoItem,
    clear_todos,
    read_todos,
    set_active_session,
    todo_read,
    todo_write,
    write_todos,
)


@pytest.fixture(autouse=True)
def reset_active_session():
    set_active_session(None)
    yield
    set_active_session(None)


class TestTodoItem:
    def test_valid(self) -> None:
        it = TodoItem(id="1", content="x", status="pending")
        assert it.status == "pending"

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError):
            TodoItem(id="1", content="x", status="bogus")


class TestReadWrite:
    def test_empty_initially(self) -> None:
        assert read_todos("session-empty") == []

    def test_round_trip(self, tmp_path, monkeypatch) -> None:
        # Patch todo_file to use tmp
        monkeypatch.setattr(todo_mod, "todo_file", lambda sid: tmp_path / f"{sid}.json")
        items = [
            TodoItem(id="1", content="first", status="pending"),
            TodoItem(id="2", content="second", status="in_progress"),
        ]
        write_todos("s1", items)
        loaded = read_todos("s1")
        assert len(loaded) == 2
        assert loaded[0].content == "first"
        assert loaded[1].status == "in_progress"

    def test_clear(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(todo_mod, "todo_file", lambda sid: tmp_path / f"{sid}.json")
        write_todos("s1", [TodoItem(id="1", content="x", status="pending")])
        clear_todos("s1")
        assert read_todos("s1") == []


class TestToolFunctions:
    def test_todo_write_uses_active_session(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(todo_mod, "todo_file", lambda sid: tmp_path / f"{sid}.json")
        set_active_session("active-1")
        result = todo_write([{"id": "1", "content": "x", "status": "pending"}])
        assert "wrote 1 todos" in result
        items = read_todos("active-1")
        assert len(items) == 1

    def test_todo_write_no_session(self) -> None:
        result = todo_write([{"id": "1", "content": "x"}])
        assert "Error" in result

    def test_todo_read_format(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(todo_mod, "todo_file", lambda sid: tmp_path / f"{sid}.json")
        set_active_session("s")
        todo_write([
            {"id": "1", "content": "first", "status": "pending"},
            {"id": "2", "content": "second", "status": "in_progress"},
            {"id": "3", "content": "third", "status": "completed"},
            {"id": "4", "content": "fourth", "status": "cancelled"},
        ])
        out = todo_read()
        assert "[ ] 1 first" in out
        assert "[*] 2 second" in out
        assert "[x] 3 third" in out
        assert "[-] 4 fourth" in out

    def test_todo_read_empty(self) -> None:
        set_active_session("nonexistent-session")
        assert todo_read() == "(no todos)"


class TestStatusValidation:
    def test_all_statuses_work(self) -> None:
        for status in TODO_STATUSES:
            it = TodoItem(id="1", content="x", status=status)
            assert it.status == status

class TestSessionIsolation:
    """Two sessions must not see each other's todos (Plan J thread-safety)."""

    def test_two_sessions_have_independent_lists(self, tmp_path, monkeypatch) -> None:
        from eaccode import todo as todo_mod
        monkeypatch.setattr(todo_mod, "todo_file", lambda sid: tmp_path / f"{sid}.json")
        todo_mod.todo_write([{"id": "1", "content": "alice-task", "status": "pending"}], session_id="alice")
        todo_mod.todo_write([{"id": "2", "content": "bob-task", "status": "pending"}], session_id="bob")
        alice = todo_mod.read_todos("alice")
        bob = todo_mod.read_todos("bob")
        assert len(alice) == 1 and alice[0].content == "alice-task"
        assert len(bob) == 1 and bob[0].content == "bob-task"
