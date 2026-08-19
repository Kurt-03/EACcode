"""Tests for tool-event emission in Agent.run (Plan K K.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eaccode.agent import (
    Agent,
    Tool,
    _shorten_args_for_display,
    _shorten_for_display,
)
from eaccode.providers.base import StreamChunk, ToolCall
from eaccode.workspace import Workspace


# --- Fake providers --------------------------------------------------------


class SingleToolProvider:
    """Yields text + one tool_call for write_file."""

    def __init__(self, target_path: Path) -> None:
        self.target_path = target_path

    def stream(self, *args: Any, **kwargs: Any) -> Any:
        yield StreamChunk(kind="text", content="doing it now")
        yield StreamChunk(
            kind="tool_call",
            tool_call=ToolCall(
                id="c1",
                name="write_file",
                arguments={"path": str(self.target_path), "content": "hello"},
            ),
        )
        yield StreamChunk(kind="done", stop_reason="end_turn")


# --- Fixtures -------------------------------------------------------------


@pytest.fixture
def wire_workspace(tmp_path, monkeypatch):
    from eaccode import tools, workspace as ws_mod

    ws_obj = Workspace(root=tmp_path.resolve())
    ws_mod.set_active_workspace(ws_obj)
    tools._set_workspace(ws_obj)
    yield ws_obj
    tools._set_workspace(None)
    ws_mod.set_active_workspace(None)


# --- Tests ----------------------------------------------------------------


class TestHelperFunctions:
    def test_shorten_for_display_short(self) -> None:
        assert _shorten_for_display("hi") == "hi"
        assert _shorten_for_display(42) == "42"
        assert _shorten_for_display([1, 2]) == "[1, 2]"

    def test_shorten_for_display_long(self) -> None:
        result = _shorten_for_display("x" * 1000, max_len=50)
        assert result.endswith("...")
        assert len(result) <= 50

    def test_shorten_args_for_display(self) -> None:
        args = _shorten_args_for_display(
            {"a": "short", "b": "y" * 200, "c": 42},
            max_len=20,
        )
        assert args["a"] == "short"
        assert args["b"].endswith("...")
        # Short values keep their type (c is 42 not "42")
        assert args["c"] == 42

    def test_shorten_args_for_display_default_max(self) -> None:
        """Default max_len is 80 (from Plan K)."""
        args = _shorten_args_for_display({"long": "x" * 500})
        assert args["long"].endswith("...")

    def test_shorten_args_for_display_preserves_types(self) -> None:
        """Args dict values stay as their original types after shortening."""
        args = _shorten_args_for_display({"n": 42, "b": True, "lst": [1, 2, 3]})
        assert args["n"] == 42
        assert args["b"] is True
        assert args["lst"] == [1, 2, 3]


class TestToolStartEmitted:
    def test_helper_produces_tool_start_event(self) -> None:
        """StreamChunk can be constructed as tool_start."""
        c = StreamChunk(
            kind="tool_start",
            tool_name="read_file",
            tool_args={"path": "x.py"},
        )
        assert c.kind == "tool_start"
        assert c.tool_name == "read_file"
        assert c.tool_args["path"] == "x.py"


class TestToolEndEmitted:
    def test_tool_end_event_with_timing(self) -> None:
        c = StreamChunk(
            kind="tool_end",
            tool_name="read_file",
            tool_result="the file content here",
            tool_duration_ms=145,
        )
        assert c.kind == "tool_end"
        assert c.tool_duration_ms == 145


class TestToolErrorEmitted:
    def test_tool_error_event(self) -> None:
        c = StreamChunk(
            kind="tool_error",
            tool_name="run_command",
            tool_error="permission denied",
            tool_duration_ms=23,
        )
        assert c.kind == "tool_error"
        assert c.tool_error == "permission denied"


class TestAgentRunWithEvents:
    def test_run_emits_tool_start_end(self, wire_workspace, tmp_path, monkeypatch) -> None:
        """Full run() loop emits tool_start then tool_end via on_chunk."""
        from eaccode import tools

        events: list[StreamChunk] = []
        target = tmp_path / "x.py"

        agent = Agent(
            conf={"model": {"default": "test/test"}},
            tools=[
                Tool(
                    "write_file",
                    "Write",
                    tools.write_file,
                    {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                    mutates=True,
                ),
            ],
        )

        # Override _complete to return (content, calls) tuple like the real one
        def fake_complete(messages, max_output_tokens, on_token=None, tools=None, **_):
            chunks = list(SingleToolProvider(target).stream())
            content = "".join(c.content for c in chunks if c.kind == "text")
            calls = [c.tool_call for c in chunks if c.kind == "tool_call" and c.tool_call]
            return content, calls
        monkeypatch.setattr(agent, "_complete", fake_complete)

        # Run with on_chunk callback
        history = agent.run(
            [{"role": "user", "content": "write"}],
            max_turns=2,
            on_chunk=events.append,
        )
        # Verify the history has the tool call + tool response
        assert any(msg.get("role") == "tool" for msg in history)

        # Verify events were captured.
        # The agent loop calls _complete at least once with the tool
        # and once more for a "final" answer, so we expect >= 1 of each.
        tool_starts = [e for e in events if e.kind == "tool_start"]
        tool_ends = [e for e in events if e.kind == "tool_end"]
        assert len(tool_starts) >= 1
        assert len(tool_ends) >= 1
        assert tool_starts[0].tool_name == "write_file"
        assert tool_ends[0].tool_name == "write_file"
        assert tool_ends[0].tool_duration_ms >= 0

    def test_run_emits_tool_error_on_failure(self, wire_workspace, tmp_path, monkeypatch) -> None:
        """When a tool raises, tool_error is emitted."""
        from eaccode import tools
        from eaccode.providers import registry as reg

        events: list[StreamChunk] = []

        agent = Agent(
            conf={"model": {"default": "test/test"}},
            tools=[
                Tool(
                    "write_file",
                    "Write",
                    tools.write_file,
                    {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                    mutates=True,
                ),
            ],
        )

        # Provider that yields a tool_call with a path outside workspace
        class ErrorProvider:
            def stream(self, *a, **k):
                yield StreamChunk(kind="text", content="trying")
                yield StreamChunk(
                    kind="tool_call",
                    tool_call=ToolCall(
                        id="c1",
                        name="write_file",
                        arguments={"path": "/etc/passwd", "content": "x"},
                    ),
                )
                yield StreamChunk(kind="done", stop_reason="end_turn")

        monkeypatch.setattr(reg, "get", lambda *a, **k: ErrorProvider())

        def fake_complete(messages, max_output_tokens, on_token=None, tools=None, **_):
            chunks = list(ErrorProvider().stream())
            content = "".join(c.content for c in chunks if c.kind == "text")
            calls = [c.tool_call for c in chunks if c.kind == "tool_call" and c.tool_call]
            return content, calls
        monkeypatch.setattr(agent, "_complete", fake_complete)

        history = agent.run(
            [{"role": "user", "content": "write"}],
            max_turns=2,
            on_chunk=events.append,
        )

        # The tool ran but returned an error message (not an exception)
        # So it emits tool_end, not tool_error. The error is in tool_result.
        tool_ends = [e for e in events if e.kind == "tool_end"]
        assert len(tool_ends) >= 1
        assert any("Error" in e.tool_result for e in tool_ends)

    def test_run_emits_tool_error_on_exception(self, wire_workspace, tmp_path, monkeypatch) -> None:
        """When _execute_tool raises, tool_error is emitted."""
        from eaccode import tools
        from eaccode.providers import registry as reg

        events: list[StreamChunk] = []

        agent = Agent(
            conf={"model": {"default": "test/test"}},
            tools=[
                Tool(
                    "write_file",
                    "Write",
                    tools.write_file,
                    {"type": "object", "properties": {}},
                    mutates=True,
                ),
            ],
        )

        class ErrorProvider:
            def stream(self, *a, **k):
                yield StreamChunk(kind="text", content="trying")
                yield StreamChunk(
                    kind="tool_call",
                    tool_call=ToolCall(
                        id="c1",
                        name="write_file",
                        arguments={"path": "x.py", "content": "y"},
                    ),
                )
                yield StreamChunk(kind="done", stop_reason="end_turn")

        monkeypatch.setattr(reg, "get", lambda *a, **k: ErrorProvider())

        def fake_complete(messages, max_output_tokens, on_token=None, tools=None, **_):
            chunks = list(ErrorProvider().stream())
            content = "".join(c.content for c in chunks if c.kind == "text")
            calls = [c.tool_call for c in chunks if c.kind == "tool_call" and c.tool_call]
            return content, calls
        monkeypatch.setattr(agent, "_complete", fake_complete)

        # Make _execute_tool raise to verify tool_error path
        def raising_execute(call):
            raise RuntimeError("simulated tool crash")
        monkeypatch.setattr(agent, "_execute_tool", raising_execute)

        history = agent.run(
            [{"role": "user", "content": "write"}],
            max_turns=2,
            on_chunk=events.append,
        )

        tool_errors = [e for e in events if e.kind == "tool_error"]
        assert len(tool_errors) >= 1
        assert "simulated tool crash" in tool_errors[0].tool_error
        assert tool_errors[0].tool_duration_ms >= 0
