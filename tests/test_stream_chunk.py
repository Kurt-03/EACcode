"""Tests for StreamChunk tool-lifecycle fields (Plan K K.1)."""

from __future__ import annotations

import pytest

from eaccode.providers.base import StreamChunk, ToolCall


class TestStreamChunkToolLifecycle:
    def test_defaults(self) -> None:
        c = StreamChunk(kind="text")
        assert c.tool_name == ""
        assert c.tool_args == {}
        assert c.tool_result == ""
        assert c.tool_duration_ms == 0
        assert c.tool_error == ""

    def test_tool_start_event(self) -> None:
        c = StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "src/main.py"},
        )
        assert c.kind == "tool_start"
        assert c.tool_name == "read_file"
        assert c.tool_args["path"] == "src/main.py"

    def test_tool_end_event(self) -> None:
        c = StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="the file content here",
            tool_duration_ms=145,
        )
        assert c.kind == "tool_end"
        assert c.tool_name == "read_file"
        assert c.tool_duration_ms == 145
        assert "content" in c.tool_result

    def test_tool_error_event(self) -> None:
        c = StreamChunk(
            kind="tool_error",
            tool_name="run_command",
            tool_error="permission denied",
            tool_duration_ms=23,
        )
        assert c.kind == "tool_error"
        assert c.tool_error == "permission denied"

    def test_text_event_unchanged(self) -> None:
        c = StreamChunk(kind="text", content="hello world")
        assert c.content == "hello world"
        assert c.tool_name == ""

    def test_tool_call_event_with_args(self) -> None:
        """Provider-emitted tool_call (from stream) still works."""
        c = StreamChunk(
            kind="tool_call",
            tool_call=ToolCall(id="x", name="write_file", arguments={"path": "x.py"}),
        )
        assert c.tool_call is not None
        assert c.tool_call.name == "write_file"

    def test_tool_args_with_complex_types(self) -> None:
        """tool_args accepts nested dicts/lists."""
        c = StreamChunk(
            kind="tool_start",
            tool_name="patch_multiple",
            tool_args={"edits": [{"path": "a.py"}, {"path": "b.py"}]},
        )
        assert isinstance(c.tool_args["edits"], list)
        assert len(c.tool_args["edits"]) == 2

    def test_done_event_still_works(self) -> None:
        c = StreamChunk(kind="done", stop_reason="end_turn")
        assert c.kind == "done"
        assert c.stop_reason == "end_turn"