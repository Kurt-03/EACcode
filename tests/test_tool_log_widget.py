"""Tests for ToolLogWidget (Plan K K.4)."""

from __future__ import annotations

import pytest

from eaccode.providers.base import StreamChunk
from eaccode.tool_log_widget import ToolLogWidget


class TestToolLogWidget:
    def test_init_empty(self) -> None:
        w = ToolLogWidget()
        assert w._entries == []

    def test_text_chunk_recorded(self) -> None:
        """Text chunks appear in the log so the user sees the full output."""
        w = ToolLogWidget()
        w.on_chunk(StreamChunk(kind="text", content="hello"))
        assert len(w._entries) == 1
        assert w._entries[0] == "hello"

    def test_tool_start_added(self) -> None:
        w = ToolLogWidget()
        w.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "x.py"},
        ))
        assert len(w._entries) == 1
        assert "read_file" in w._entries[0]

    def test_tool_end_added(self) -> None:
        w = ToolLogWidget()
        w.on_chunk(StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="content",
            tool_duration_ms=42,
        ))
        assert len(w._entries) == 1
        assert "42ms" in w._entries[0]

    def test_tool_error_added(self) -> None:
        w = ToolLogWidget()
        w.on_chunk(StreamChunk(
            kind="tool_error",
            tool_name="run_command",
            tool_error="denied",
            tool_duration_ms=10,
        ))
        assert len(w._entries) == 1
        assert "denied" in w._entries[0]

    def test_max_entries_trim(self) -> None:
        w = ToolLogWidget()
        w.max_entries = 3
        for i in range(5):
            w.on_chunk(StreamChunk(
                kind="tool_start",
                tool_name="t",
                tool_args={"i": i},
            ))
        assert len(w._entries) == 3
        # Last 3 entries
        # The text-format uses str() on the value, so i becomes '0'..'4'
        assert "i=0" not in "\n".join(w._entries)  # first one is trimmed
        assert "i='4'" in w._entries[-1]

    def test_clear(self) -> None:
        w = ToolLogWidget()
        w.on_chunk(StreamChunk(kind="tool_start", tool_name="t"))
        assert len(w._entries) == 1
        w.clear()
        assert w._entries == []