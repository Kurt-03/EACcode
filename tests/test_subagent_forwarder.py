"""Tests for sub-agent chunk forwarding (Plan K K.5)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from eaccode.providers.base import StreamChunk
from eaccode.subagents import _make_subagent_chunk_forwarder


class TestSubagentForwarder:
    def test_returns_none_when_no_parent(self) -> None:
        fwd = _make_subagent_chunk_forwarder("task", "sub-key", None)
        assert fwd is None

    def test_text_chunk_passes_through(self) -> None:
        captured: list = []
        fwd = _make_subagent_chunk_forwarder("task", "sub-key", captured.append)
        fwd(StreamChunk(kind="text", content="hello"))
        assert len(captured) == 1
        assert captured[0].content == "hello"

    def test_tool_start_gets_indent_marker(self) -> None:
        captured: list = []
        fwd = _make_subagent_chunk_forwarder("task", "sub-key", captured.append)
        fwd(StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "x.py"},
        ))
        assert len(captured) == 1
        # Sub-agent tools get a '  ↳ ' prefix to show nesting
        assert "↳" in captured[0].tool_name
        assert "read_file" in captured[0].tool_name

    def test_tool_end_gets_indent_marker(self) -> None:
        captured: list = []
        fwd = _make_subagent_chunk_forwarder("task", "sub-key", captured.append)
        fwd(StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="content",
            tool_duration_ms=10,
        ))
        assert "↳" in captured[0].tool_name

    def test_tool_error_gets_indent_marker(self) -> None:
        captured: list = []
        fwd = _make_subagent_chunk_forwarder("task", "sub-key", captured.append)
        fwd(StreamChunk(
            kind="tool_error",
            tool_name="run_command",
            tool_error="denied",
        ))
        assert "↳" in captured[0].tool_name

    def test_done_chunk_silent(self) -> None:
        captured: list = []
        fwd = _make_subagent_chunk_forwarder("task", "sub-key", captured.append)
        fwd(StreamChunk(kind="done"))
        # done is silent in the renderer, but should still pass through
        assert len(captured) == 1
        assert captured[0].kind == "done"

    def test_error_chunk_passes_through(self) -> None:
        captured: list = []
        fwd = _make_subagent_chunk_forwarder("task", "sub-key", captured.append)
        fwd(StreamChunk(kind="error", content="HTTP 500"))
        assert captured[0].content == "HTTP 500"