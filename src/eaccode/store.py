"""Session store (Phase B3): SQLite + FTS5 persistence for conversations.

Sessions survive restarts and are full-text searchable — the foundation
for recalling past work (Discovery / Scroll / Browse).
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from eaccode import config as cfg
from eaccode.agent import Tool

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'cli'
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content, content='messages', content_rowid='id',
    tokenize='unicode61'
);
"""

_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content)
    VALUES ('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
"""


@dataclass
class SessionInfo:
    id: str
    title: str
    started_at: str
    message_count: int


@dataclass
class SearchHit:
    session_id: str
    title: str
    started_at: str
    snippet: str
    matches: int


def db_path() -> Path:
    """Path to the sessions database."""
    return cfg.data_dir() / "sessions.db"


def _connect(db: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db or db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db: Path | None = None) -> None:
    """Create schema (sessions, messages, FTS index with triggers)."""
    conn = _connect(db)
    try:
        conn.executescript(_SCHEMA)
        try:
            conn.executescript(_FTS_SCHEMA)
            conn.executescript(_FTS_TRIGGERS)
            conn.execute("INSERT INTO messages_fts(messages_fts) VALUES ('rebuild')")
        except sqlite3.OperationalError:
            pass  # FTS5 unavailable -> LIKE fallback in search()
        conn.commit()
    finally:
        conn.close()


def _fts_available(db: Path) -> bool:
    try:
        conn = _connect(db)
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='messages_fts'"
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def new_session(platform: str = "cli", title: str = "", db: Path | None = None) -> str:
    """Create a session; returns its id."""
    init_db(db)
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    conn = _connect(db)
    try:
        conn.execute(
            "INSERT INTO sessions (id, title, started_at, platform) VALUES (?, ?, ?, ?)",
            (session_id, title, datetime.now().isoformat(timespec="seconds"), platform),
        )
        conn.commit()
    finally:
        conn.close()
    return session_id


def set_title(session_id: str, title: str, db: Path | None = None) -> None:
    """Update a session's title (first user message, truncated)."""
    conn = _connect(db)
    try:
        conn.execute("UPDATE sessions SET title = ? WHERE id = ?", (title[:120], session_id))
        conn.commit()
    finally:
        conn.close()


def add_message(session_id: str, role: str, content: str, db: Path | None = None) -> int:
    """Append a message; returns its rowid."""
    conn = _connect(db)
    try:
        cursor = conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def browse(limit: int = 10, db: Path | None = None) -> list[SessionInfo]:
    """Most recent sessions with message counts."""
    init_db(db)
    conn = _connect(db)
    try:
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.started_at, COUNT(m.id) AS n
            FROM sessions s LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id ORDER BY s.rowid DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            SessionInfo(
                id=r["id"],
                title=r["title"],
                started_at=r["started_at"],
                message_count=r["n"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def show(session_id: str, db: Path | None = None) -> list[dict[str, str]]:
    """All messages of a session, oldest first."""
    init_db(db)
    conn = _connect(db)
    try:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]
    finally:
        conn.close()


def scroll(
    session_id: str,
    around_message_id: int | None = None,
    window: int = 5,
    db: Path | None = None,
) -> list[dict[str, Any]]:
    """Messages of a session with ids; anchored around a message or latest.

    Returns entries with ``id``, ``role``, ``content``, ``created_at``.
    Without an anchor the most recent ``window`` messages are returned.
    """
    init_db(db)
    conn = _connect(db)
    try:
        if around_message_id is not None:
            rows = conn.execute(
                """
                SELECT id, role, content, created_at FROM messages
                WHERE session_id = ? AND id BETWEEN ? AND ?
                ORDER BY id
                """,
                (
                    session_id,
                    max(1, around_message_id - window),
                    around_message_id + window,
                ),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, role, content, created_at FROM messages
                WHERE session_id = ? ORDER BY id DESC LIMIT ?
                """,
                (session_id, window),
            ).fetchall()
            rows = list(reversed(rows))
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": r["content"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def search(query: str, limit: int = 5, db: Path | None = None) -> list[SearchHit]:
    """Full-text search across all sessions (FTS5, LIKE fallback)."""
    init_db(db)
    hits: list[SearchHit] = []
    if _fts_available(db):
        hits = _search_fts(query, limit, db)
    if not hits:
        hits = _search_like(query, limit, db)
    return hits


def _search_fts(query: str, limit: int, db: Path) -> list[SearchHit]:
    conn = _connect(db)
    try:
        escaped = query.replace('"', '""')
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.started_at,
                   snippet(messages_fts, 0, '[', ']', '…', 12) AS snip,
                   COUNT(*) OVER (PARTITION BY s.id) AS matches
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            JOIN sessions s ON s.id = m.session_id
            WHERE messages_fts MATCH ?
            GROUP BY s.id
            ORDER BY matches DESC, s.rowid DESC
            LIMIT ?
            """,
            (f'"{escaped}"', limit),
        ).fetchall()
        return [
            SearchHit(
                session_id=r["id"],
                title=r["title"] or "(untitled)",
                started_at=r["started_at"],
                snippet=r["snip"] or "",
                matches=int(r["matches"]),
            )
            for r in rows
        ]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _search_like(query: str, limit: int, db: Path) -> list[SearchHit]:
    conn = _connect(db)
    try:
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.started_at, COUNT(*) AS matches
            FROM messages m JOIN sessions s ON s.id = m.session_id
            WHERE m.content LIKE ?
            GROUP BY s.id ORDER BY matches DESC, s.rowid DESC LIMIT ?
            """,
            (f"%{query}%", limit),
        ).fetchall()
        return [
            SearchHit(
                session_id=r["id"],
                title=r["title"] or "(untitled)",
                started_at=r["started_at"],
                snippet="",
                matches=int(r["matches"]),
            )
            for r in rows
        ]
    finally:
        conn.close()


def _tool_session_search(query: str) -> str:
    """Agent-facing search: past sessions as readable text."""
    hits = search(query)
    if not hits:
        return f"(no sessions match: {query})"
    return "\n".join(
        f"{hit.session_id}: {hit.title} ({hit.started_at}, {hit.matches} hits)"
        + (f"\n  …{hit.snippet}…" if hit.snippet else "")
        for hit in hits
    )


def _tool_session_scroll(session_id: str, window: int = 8) -> str:
    """Agent-facing scroll: the most recent messages of one session."""
    messages = scroll(session_id, window=window)
    if not messages:
        return f"(no session or empty: {session_id})"
    return "\n".join(
        f"[{m['role']}] {m['content']}" for m in messages
    )


def make_session_tools() -> list[Tool]:
    """Agent tools for the session store (B3)."""
    return [
        Tool(
            "session_search",
            "Search past conversations for a phrase; returns matching "
            "sessions with snippets (FTS5 search on the SQLite session "
            "store). Returns '@session:<id> <snippet>' lines per match, "
            "or '(no matches)' when nothing is found. Use the session id "
            "with session_scroll to read full context.",
            _tool_session_search,
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Free-text search query. Supports quotes for "
                            "phrases and prefix wildcards (terms*)."
                        ),
                    },
                },
                "required": ["query"],
            },
            mutates=False,
        ),
        Tool(
            "session_scroll",
            "Read the most recent messages of a session (use the session "
            "id from session_search). Returns 'role: content' lines plus a "
            "session header. Returns 'Error: session not found' when id "
            "is invalid.",
            _tool_session_scroll,
            {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": (
                            "Session id (from a prior session_search, or "
                            "@session:<id> reference in user input)."
                        ),
                    },
                    "window": {
                        "type": "integer",
                        "description": (
                            "Maximum number of messages to return, "
                            "starting from the most recent (default: 20)."
                        ),
                    },
                },
                "required": ["session_id"],
            },
            mutates=False,
        ),
    ]
