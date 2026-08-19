"""Base types for provider adapters.

StreamChunk is the normalized wire-format stream event the agent
sees. Each provider adapter maps its native SDK events to StreamChunk
instances; the agent downstream never touches anthropic/openai types.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    """A single tool invocation requested by the model.

    Accumulated across multiple content_block_delta events for the
    same index when the input_json is split across chunks.
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamChunk:
    """One normalized event from any provider (Plan K: extended).

    kind:
      - "text":       regular answer content (delta.text)
      - "reasoning":  reasoning content (delta.thinking / delta.reasoning_content)
      - "tool_call":  a tool invocation from the model, possibly partial
                       (id may be empty if the assistant has not yet sent input)
      - "tool_start": a tool call is about to execute (Plan K)
      - "tool_end":   tool execution finished successfully (Plan K)
      - "tool_error": tool execution raised an exception (Plan K)
      - "usage":      token counts (input_tokens, output_tokens)
      - "done":       stream end

    Tool-event fields (tool_start/tool_end/tool_error):
      - tool_name:    str   name of the tool
      - tool_args:    dict  short preview of args (already truncated)
      - tool_result:  str   short preview of result
      - tool_duration_ms: int  how long the call took
      - tool_error:   str   error message for tool_error chunks
    """

    kind: str
    content: str = ""
    tool_call: ToolCall | None = None
    usage: dict[str, int] = field(default_factory=dict)
    stop_reason: str = ""
    # Plan K: tool lifecycle
    tool_name: str = ""
    tool_args: dict[str, object] = field(default_factory=dict)
    tool_result: str = ""
    tool_duration_ms: int = 0
    tool_error: str = ""


class Provider(Protocol):
    """Provider adapter protocol.

    A real adapter implements ``stream(messages, **kwargs)`` returning an
    iterator of StreamChunks. ``complete(...)`` is an optional non-streaming
    helper used by tools that need a single-shot response.
    """

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        cancel_event: Any | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Iterator[StreamChunk]:
        ...
