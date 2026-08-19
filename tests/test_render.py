"""Tests for render module (Plan K K.3)."""

from __future__ import annotations

import pytest

from eaccode.providers.base import StreamChunk, ToolCall
from eaccode.render import (
    SECRET_KEYS,
    TOOL_ICONS,
    redact_secrets,
    render_chunk,
    tool_icon,
)


class TestToolIcon:
    def test_known_tool(self) -> None:
        assert tool_icon("read_file") == "📖"
        assert tool_icon("write_file") == "✏️"
        assert tool_icon("run_command") == "⚙️"

    def test_unknown_tool(self) -> None:
        assert tool_icon("mystery_tool") == "🔧"


class TestRedactSecrets:
    def test_redacts_api_key(self) -> None:
        result = redact_secrets({"api_key": "sk-secret-1234", "path": "x.py"})
        assert result["api_key"] == "***REDACTED***"
        assert result["path"] == "x.py"

    def test_redacts_password(self) -> None:
        result = redact_secrets({"password": "hunter2", "host": "localhost"})
        assert result["password"] == "***REDACTED***"
        assert result["host"] == "localhost"

    def test_redacts_token(self) -> None:
        result = redact_secrets({"auth_token": "abc123"})
        assert result["auth_token"] == "***REDACTED***"

    def test_does_not_redact_safe_keys(self) -> None:
        result = redact_secrets({"path": "x.py", "name": "test", "count": 5})
        assert result == {"path": "x.py", "name": "test", "count": 5}

    def test_secret_keys_defined(self) -> None:
        assert "api_key" in SECRET_KEYS
        assert "password" in SECRET_KEYS
        assert "token" in SECRET_KEYS


class TestRenderChunk:
    def test_text_chunk(self) -> None:
        c = StreamChunk(kind="text", content="hello world")
        out = render_chunk(c, verbose=True)
        assert out == "hello world"

    def test_text_chunk_verbose_off(self) -> None:
        c = StreamChunk(kind="text", content="hello")
        out = render_chunk(c, verbose=False)
        assert out == "hello"  # text always shown

    def test_tool_start(self) -> None:
        c = StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "x.py"},
        )
        out = render_chunk(c, verbose=True)
        assert "read_file" in out
        assert "x.py" in out

    def test_tool_start_off(self) -> None:
        c = StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "x.py"},
        )
        out = render_chunk(c, verbose=False)
        assert out is None

    def test_tool_end_with_timing(self) -> None:
        c = StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="the content",
            tool_duration_ms=145,
        )
        out = render_chunk(c, verbose=True)
        assert "145ms" in out
        assert "the content" in out

    def test_tool_error(self) -> None:
        c = StreamChunk(
            kind="tool_error",
            tool_name="run_command",
            tool_error="permission denied",
            tool_duration_ms=23,
        )
        out = render_chunk(c, verbose=True)
        assert "permission denied" in out
        assert "23ms" in out

    def test_done_silent(self) -> None:
        assert render_chunk(StreamChunk(kind="done"), verbose=True) is None
        assert render_chunk(StreamChunk(kind="done"), verbose=False) is None

    def test_error_chunk(self) -> None:
        c = StreamChunk(kind="error", content="HTTP 500")
        out = render_chunk(c, verbose=True)
        assert "Error" in out
        assert "HTTP 500" in out

    def test_secrets_redacted_in_render(self) -> None:
        c = StreamChunk(
            kind="tool_start",
            tool_name="http_get",
            tool_args={"url": "https://api.example.com", "api_key": "sk-secret-1234"},
        )
        out = render_chunk(c, verbose=True)
        assert "sk-secret-1234" not in out
        assert "REDACTED" in out
        assert "api.example.com" in out  # url is not secret

    def test_long_result_truncated(self) -> None:
        c = StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="x" * 500,
            tool_duration_ms=10,
        )
        out = render_chunk(c, verbose=True)
        assert "..." in out
        # Truncation should be present
        assert len(out) < 500

    def test_tool_icons_defined(self) -> None:
        assert "read_file" in TOOL_ICONS
        assert "write_file" in TOOL_ICONS
        assert "run_command" in TOOL_ICONS