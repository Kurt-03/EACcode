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
    """One normalized event from any provider.

    kind:
      - "text":       regular answer content (delta.text)
      - "reasoning":  reasoning content (delta.thinking / delta.reasoning_content)
      - "tool_call":  a tool invocation, possibly partial (id may be empty
                       if the assistant has not yet sent input)
      - "usage":      token counts (input_tokens, output_tokens)
      - "done":       stream end
    """

    kind: str
    content: str = ""
    tool_call: ToolCall | None = None
    usage: dict[str, int] = field(default_factory=dict)
    stop_reason: str = ""


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
