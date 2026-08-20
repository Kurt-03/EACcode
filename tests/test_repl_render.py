"""Tests for ReplRenderer (Plan M.2)."""

from __future__ import annotations

import io

import pytest

from eaccode.providers.base import StreamChunk
from eaccode.repl_render import ReplRenderer


@pytest.fixture
def out() -> io.StringIO:
    return io.StringIO()


@pytest.fixture
def renderer(out) -> ReplRenderer:
    return ReplRenderer(stdout=out, plain=True)  # plain=True strips colors


class TestTurnLifecycle:
    def test_turn_marker_emitted_on_first_chunk(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(kind="text", content="hi"))
        assert "●" in out.getvalue()
        assert "hi" in out.getvalue()

    def test_no_double_turn_marker(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(kind="text", content="foo"))
        renderer.on_chunk(StreamChunk(kind="text", content=" bar"))
        # Only one ● at the start
        text = out.getvalue()
        assert text.count("●") == 1

    def test_finish_emits_summary(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(kind="text", content="hi"))
        renderer.finish(duration_s=5.3)
        out_v = out.getvalue()
        assert "⏺" in out_v
        assert "5.3s" in out_v


class TestToolBlocks:
    def test_tool_start_emits_box(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "src/main.py"},
        ))
        text = out.getvalue()
        assert "⎿" in text
        assert "read_file" in text
        assert "src/main.py" in text

    def test_tool_end_closes_box(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "x.py"},
        ))
        renderer.on_chunk(StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="file content",
            tool_duration_ms=42,
        ))
        text = out.getvalue()
        assert "✓" in text
        assert "42ms" in text
        assert "file content" in text

    def test_tool_error_emits_red(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(
            kind="tool_error",
            tool_name="run_command",
            tool_error="permission denied",
            tool_duration_ms=12,
        ))
        text = out.getvalue()
        assert "✗" in text
        assert "permission denied" in text
        assert "12ms" in text

    def test_multiple_tools_counted(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="list_files",
            tool_args={"path": "src/"},
        ))
        renderer.on_chunk(StreamChunk(
            kind="tool_end",
            tool_name="list_files",
            tool_result="a.py",
            tool_duration_ms=5,
        ))
        renderer.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "src/a.py"},
        ))
        renderer.on_chunk(StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="content",
            tool_duration_ms=10,
        ))
        renderer.finish(duration_s=1.5)
        out_v = out.getvalue()
        assert "2 tools used" in out_v
        assert "1.5s" in out_v


class TestSecretsRedacted:
    def test_api_key_redacted(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="http_get",
            tool_args={"url": "https://x.com", "api_key": "sk-secret-123"},
        ))
        text = out.getvalue()
        assert "sk-secret-123" not in text
        assert "***" in text


class TestFormatting:
    def test_args_truncated(self, renderer, out) -> None:
        long_path = "x" * 200
        renderer.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": long_path},
        ))
        text = out.getvalue()
        assert "x" * 200 not in text
        assert "…" in text

    def test_result_truncated(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "x"},
        ))
        renderer.on_chunk(StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="x" * 500,
            tool_duration_ms=1,
        ))
        text = out.getvalue()
        # Long result is truncated
        assert "x" * 500 not in text

    def test_done_chunk_silent(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(kind="done"))
        assert out.getvalue() == ""


class TestSummaryDurations:
    def test_no_tools_zero_seconds_ok(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(kind="text", content="x"))
        renderer.finish(duration_s=0.4)
        assert "0.4s" in out.getvalue()

    def test_single_tool_singular(self, renderer, out) -> None:
        renderer.on_chunk(StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "x"},
        ))
        renderer.on_chunk(StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="r",
            tool_duration_ms=1,
        ))
        renderer.finish(duration_s=1.0)
        assert "1 tool used" in out.getvalue()
