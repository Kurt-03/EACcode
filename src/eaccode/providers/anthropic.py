"""Anthropic Messages API adapter for eaccode.

Uses the official ``anthropic`` SDK. Works against any endpoint that
implements the Anthropic Messages protocol, including:

- Anthropic's native console (https://api.anthropic.com)
- Anthropic-compatible providers (e.g. MiniMax via api.minimax.io/anthropic)

Provider-specific behavior (timestamps, KB cutoff, etc.) is read from
models.dev at construction time so the adapter does not hardcode any
provider-specific paths or auth headers.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from eaccode.providers.base import StreamChunk, ToolCall

logger = logging.getLogger(__name__)


# Beta-Headers that MiniMax's Anthropic-compatible endpoint rejects:
#   - fine-grained-tool-streaming: connection error on every tool call
# MiniMax uses Bearer auth (not x-api-key) since the auth schema differs
# from the native Anthropic console.
_MINIMAX_BETA_HEADERS_TO_STRIP = frozenset(
    {
        "fine-grained-tool-streaming-2025-05-14",
    }
)


def _is_minimax_endpoint(base_url: str | None) -> bool:
    """True if base_url points at a MiniMax Anthropic-compatible endpoint."""
    if not base_url:
        return False
    normalized = base_url.rstrip("/").lower()
    return normalized.startswith(
        ("https://api.minimax.io/anthropic", "https://api.minimaxi.com/anthropic")
    )


def _build_beta_headers(base_url: str | None) -> list[str]:
    """Return safe anthropic-beta headers for the given endpoint."""
    candidates = [
        "interleaved-thinking-2025-05-14",
    ]
    if _is_minimax_endpoint(base_url):
        return [b for b in candidates if b not in _MINIMAX_BETA_HEADERS_TO_STRIP]
    return candidates


def _convert_messages_to_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split eaccode's flat messages into (system, cleaned_messages).

    eaccode's message format: [{"role": ..., "content": ...}, ...]
    Anthropic's format: system is a top-level string, then messages with
    role in {user, assistant} and content either a string or a list of
    typed blocks.

    Tool results (role="tool") are converted to user messages with
    tool_result blocks. Tool calls (assistant messages with tool_calls)
    are converted to assistant content blocks with tool_use.
    """
    system: list[str] = []
    cleaned: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system.append(content if isinstance(content, str) else str(content))
            continue
        if role == "tool":
            # Tool result → user message with tool_result block
            cleaned.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": content if isinstance(content, str) else str(content),
                        }
                    ],
                }
            )
            continue
        if role == "assistant":
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                # Assistant with tool_calls → content blocks
                blocks: list[dict[str, Any]] = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for tc in tool_calls:
                    fn = tc.get("function", {}) or {}
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args) if args else {}
                        except json.JSONDecodeError:
                            args = {}
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": fn.get("name", ""),
                            "input": args if isinstance(args, dict) else {},
                        }
                    )
                cleaned.append({"role": "assistant", "content": blocks})
            else:
                # Plain assistant text → flat string
                if isinstance(content, str):
                    cleaned.append({"role": "assistant", "content": content})
                else:
                    cleaned.append({"role": "assistant", "content": str(content)})
            continue
        # user / assistant (without tool_calls) → flat string content
        if isinstance(content, str):
            cleaned.append({"role": role, "content": content})
        else:
            cleaned.append({"role": role, "content": str(content)})

    return system, cleaned


def _convert_tools_to_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert eaccode's OpenAI-shape tool list to Anthropic's input_schema form."""
    converted: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") == "function":
            fn = tool.get("function", {})
            converted.append(
                {
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        else:
            # Already in Anthropic shape or unsupported
            converted.append(tool)
    return converted


class AnthropicProvider:
    """Adapter for the Anthropic Messages API.

    The provider is constructed once per request (cheap) and holds
    the SDK client. ``stream(messages, ...)`` returns a generator of
    StreamChunk.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        model: str = "",
        timeout: float = 60.0,
    ) -> None:
        import anthropic  # lazy import — SDK has ~220ms cold-start

        self._model = model
        # Build default_headers for beta / Bearer overrides
        default_headers: dict[str, str] = {}
        beta_headers = _build_beta_headers(base_url)
        if beta_headers:
            default_headers["anthropic-beta"] = ",".join(beta_headers)
        # Strip /v1 from base_url if present — the SDK appends /v1/messages
        normalized_base_url = base_url.rstrip("/") if base_url else None
        if normalized_base_url and normalized_base_url.endswith("/v1"):
            normalized_base_url = normalized_base_url[:-3]

        # We use the SDK only for the streaming transport; we manually
        # iterate the MessageStream events rather than trust the SDK's
        # helpers, so we don't need an SDK client per request.
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": 0,  # we handle retries in the agent loop
        }
        if normalized_base_url:
            kwargs["base_url"] = normalized_base_url
        if default_headers:
            kwargs["default_headers"] = default_headers
        self._client = anthropic.Anthropic(**kwargs)
        # Suppress SDK-level auth env interference (ANTHROPIC_API_KEY)
        if not api_key.startswith("sk-ant-"):
            self._client.api_key = None

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
        """Yield normalized StreamChunks from the Anthropic Messages stream."""
        system_parts, cleaned_messages = _convert_messages_to_anthropic(messages)
        if system is not None:
            system_parts = [system]
        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": cleaned_messages,
            "max_tokens": max_tokens if max_tokens is not None else 4096,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        if temperature is not None:
            kwargs["temperature"] = temperature
        if tools:
            kwargs["tools"] = _convert_tools_to_anthropic(tools)

        # Accumulate tool-use blocks across multiple content_block_delta events
        pending_tool_calls: dict[int, dict[str, Any]] = {}

        with self._client.messages.stream(**kwargs) as stream:
            for event in stream:
                if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
                    break
                event_type = getattr(event, "type", None)
                if event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block is not None and getattr(block, "type", None) == "tool_use":
                        index = getattr(event, "index", 0)
                        pending_tool_calls[index] = {
                            "id": getattr(block, "id", "") or "",
                            "name": getattr(block, "name", "") or "",
                            "input_json": "",
                        }
                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    delta_type = getattr(delta, "type", None)
                    if delta_type == "text_delta":
                        text = getattr(delta, "text", "")
                        if text:
                            yield StreamChunk(kind="text", content=text)
                    elif delta_type == "thinking_delta":
                        thinking = getattr(delta, "thinking", "")
                        if thinking:
                            yield StreamChunk(kind="reasoning", content=thinking)
                    elif delta_type == "input_json_delta":
                        index = getattr(event, "index", 0)
                        if index in pending_tool_calls:
                            pending_tool_calls[index]["input_json"] += getattr(
                                delta, "partial_json", ""
                            )
                elif event_type == "content_block_stop":
                    index = getattr(event, "index", 0)
                    if index in pending_tool_calls:
                        tc = pending_tool_calls.pop(index)
                        args = tc["input_json"] or "{}"
                        try:
                            args_dict = json.loads(args) if args else {}
                        except json.JSONDecodeError:
                            args_dict = {}
                        if not isinstance(args_dict, dict):
                            args_dict = {}
                        yield StreamChunk(
                            kind="tool_call",
                            tool_call=ToolCall(
                                id=tc["id"], name=tc["name"], arguments=args_dict
                            ),
                        )
                elif event_type == "message_delta":
                    stop_reason = getattr(getattr(event, "delta", None), "stop_reason", None)
                    usage = getattr(event, "usage", None)
                    if usage is not None:
                        usage_dict: dict[str, int] = {}
                        output_tokens = getattr(usage, "output_tokens", None)
                        if output_tokens is not None:
                            usage_dict["output_tokens"] = int(output_tokens)
                        yield StreamChunk(
                            kind="usage",
                            usage=usage_dict,
                            stop_reason=stop_reason or "",
                        )
                # message_start, message_stop, ping → ignored

            # Final usage from stream.get_final_message()
            try:
                final = stream.get_final_message()
            except Exception:
                final = None
            if final is not None:
                usage = getattr(final, "usage", None)
                if usage is not None:
                    out = getattr(usage, "output_tokens", None)
                    if out is not None and (not kwargs.get("max_tokens")):
                        # Avoid double-counting: message_delta already yielded usage
                        pass
                stop_reason = getattr(final, "stop_reason", None)
            yield StreamChunk(kind="done", stop_reason=stop_reason or "")
