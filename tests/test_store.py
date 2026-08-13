"""Tests for the session store (Phase B3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import config as cfg
from eaccode import store


@pytest.fixture
def tmp_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    db = tmp_path / "sessions.db"
    store.init_db(db)
    return db


class TestSessionLifecycle:
    def test_new_session_creates_row(self, tmp_store: Path) -> None:
        session_id = store.new_session(db=tmp_store)
        assert session_id
        assert store.browse(db=tmp_store)[0].id == session_id

    def test_add_and_show_messages(self, tmp_store: Path) -> None:
        session_id = store.new_session(db=tmp_store)
        store.add_message(session_id, "user", "hallo", db=tmp_store)
        store.add_message(session_id, "assistant", "hi!", db=tmp_store)
        messages = store.show(session_id, db=tmp_store)
        assert [m["role"] for m in messages] == ["user", "assistant"]
        assert messages[1]["content"] == "hi!"

    def test_set_title(self, tmp_store: Path) -> None:
        session_id = store.new_session(title="", db=tmp_store)
        store.set_title(
            session_id, "Ein langer Titel der abgeschnitten werden sollte", db=tmp_store
        )
        assert (
            store.browse(db=tmp_store)[0].title
            == "Ein langer Titel der abgeschnitten werden sollte"
        )

    def test_browse_sorted_by_recency(self, tmp_store: Path) -> None:
        first = store.new_session(db=tmp_store)
        second = store.new_session(db=tmp_store)
        store.add_message(first, "user", "alt", db=tmp_store)
        ids = [s.id for s in store.browse(db=tmp_store)]
        assert ids[0] == second
        assert ids[1] == first
        assert store.browse(db=tmp_store)[1].message_count == 1

    def test_show_unknown_session_empty(self, tmp_store: Path) -> None:
        assert store.show("gibtsnicht", db=tmp_store) == []


class TestSearch:
    def test_search_finds_session(self, tmp_store: Path) -> None:
        session_id = store.new_session(title="Router-Bau", db=tmp_store)
        store.add_message(session_id, "user", "Wie baue ich den Router?", db=tmp_store)
        store.add_message(session_id, "assistant", "Mit LiteLLM und Fallback-Chain.", db=tmp_store)
        hits = store.search("LiteLLM", db=tmp_store)
        assert len(hits) == 1
        assert hits[0].session_id == session_id
        assert hits[0].matches >= 1

    def test_search_no_hits(self, tmp_store: Path) -> None:
        store.new_session(title="x", db=tmp_store)
        store.add_message(
            store.browse(db=tmp_store)[0].id, "user", "nichts relevantes", db=tmp_store
        )
        assert store.search("gibtsnicht", db=tmp_store) == []

    def test_search_multiple_sessions_ranked(self, tmp_store: Path) -> None:
        a = store.new_session(title="a", db=tmp_store)
        b = store.new_session(title="b", db=tmp_store)
        store.add_message(a, "user", "eins zwei drei", db=tmp_store)
        for _ in range(3):
            store.add_message(b, "user", "eins zwei drei", db=tmp_store)
        hits = store.search("eins zwei drei", db=tmp_store)
        assert hits[0].session_id == b  # mehr Treffer zuerst

    def test_search_like_fallback_without_fts(
        self, tmp_store: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        session_id = store.new_session(db=tmp_store)
        store.add_message(session_id, "user", "das ist ein Testbegriff", db=tmp_store)
        monkeypatch.setattr(store, "_fts_available", lambda db: False)
        hits = store.search("Testbegriff", db=tmp_store)
        assert len(hits) == 1
        assert hits[0].session_id == session_id


class TestSessionTool:
    def test_session_search_tool_finds_sessions(self, tmp_store: Path) -> None:
        session_id = store.new_session(title="Alte Arbeit", db=tmp_store)
        store.add_message(session_id, "user", "Wir haben den Router gebaut", db=tmp_store)
        tools = store.make_session_tools()
        tool = next(t for t in tools if t.name == "session_search")
        out = tool.func(query="Router")
        assert "Alte Arbeit" in out
        assert session_id in out

    def test_session_search_tool_no_hits(self, tmp_store: Path) -> None:
        tools = store.make_session_tools()
        tool = next(t for t in tools if t.name == "session_search")
        assert "no sessions match" in tool.func(query="gibtsnicht")
