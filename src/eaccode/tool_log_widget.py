"""Tool-call log widget for TUI (Plan K K.4 simplified).

A scrolling list of tool calls + results. Each entry shows:
- icon + tool name + args (truncated)
- duration
- result preview
"""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from eaccode.providers.base import StreamChunk
from eaccode.render import render_chunk, tool_icon


class ToolLogWidget(Static):
    """Scrolling list of tool calls.

    Receives StreamChunks via the ``on_chunk`` callback wired up by
    the App. Renders tool_start / tool_end / tool_error events.
    """

    DEFAULT_CSS = """
    ToolLogWidget {
        height: auto;
        max-height: 50%;
        overflow-y: auto;
        border: solid green;
        padding: 0 1;
    }
    """

    max_entries: reactive[int] = reactive(50)

    def __init__(self, **kwargs) -> None:
        super().__init__("**Tool Log:**\n", **kwargs)
        self._entries: list[str] = []

    def on_chunk(self, chunk: StreamChunk) -> None:
        """Handle a stream chunk from the agent."""
        rendered = render_chunk(chunk, verbose=True)
        if rendered is None:
            return
        self._entries.append(rendered)
        # Trim
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]
        # Re-render
        self.update("\n".join(self._entries))

    def clear(self) -> None:
        self._entries = []
        self.update("**Tool Log:**\n")
