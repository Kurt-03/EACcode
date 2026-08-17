"""Tests for the Anthropic provider adapter."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from eaccode.providers import anthropic as anthropic_mod
from eaccode.providers.anthropic import (
    AnthropicProvider,
    _build_beta_headers,
    _convert_messages_to_anthropic,
    _convert_tools_to_anthropic,
    _is_minimax_endpoint,
)
from eaccode.providers.base import StreamChunk


# ---------------------------------------------------------------------------
# Message/tool conversion
# ---------------------------------------------------------------------------


class TestMessageConversion:
    def test_simple_messages_extract_system(self) -> None:
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        system, cleaned = _convert_messages_to_anthropic(msgs)
        assert system == ["You are helpful."]
        assert cleaned == [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]

    def test_tool_call_assistant_converted_to_blocks(self) -> None:
        msgs = [
            {
                "role": "assistant",
                "content": "Let me check the weather.",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "get_weather",
                            "arguments": {"location": "Berlin"},
                        },
                    }
                ],
            }
        ]
        _, cleaned = _convert_messages_to_anthropic(msgs)
        assert cleaned[0]["content"] == [
            {"type": "text", "text": "Let me check the weather."},
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "get_weather",
                "input": {"location": "Berlin"},
            },
        ]

    def test_tool_call_arguments_string_parsed(self) -> None:
        msgs = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "f",
                            "arguments": '{"x": 1}',  # JSON string
                        },
                    }
                ],
            }
        ]
        _, cleaned = _convert_messages_to_anthropic(msgs)
        assert cleaned[0]["content"][0]["input"] == {"x": 1}

    def test_tool_call_arguments_invalid_json_fallback(self) -> None:
        msgs = [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "f", "arguments": "not json"},
                    }
                ],
            }
        ]
        _, cleaned = _convert_messages_to_anthropic(msgs)
        assert cleaned[0]["content"][0]["input"] == {}

    def test_tool_result_converted_to_user_message(self) -> None:
        msgs = [
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "Result: 22°C",
            }
        ]
        _, cleaned = _convert_messages_to_anthropic(msgs)
        assert cleaned[0] == {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": "Result: 22°C",
                }
            ],
        }

    def test_multiple_system_messages_joined(self) -> None:
        msgs = [
            {"role": "system", "content": "Rule 1."},
            {"role": "system", "content": "Rule 2."},
        ]
        system, _ = _convert_messages_to_anthropic(msgs)
        assert system == ["Rule 1.", "Rule 2."]


class TestToolConversion:
    def test_openai_function_to_anthropic(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "f",
                    "description": "desc",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        converted = _convert_tools_to_anthropic(tools)
        assert converted == [
            {
                "name": "f",
                "description": "desc",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

    def test_passthrough_passthrough(self) -> None:
        tools = [{"name": "f", "description": "d", "input_schema": {"type": "object"}}]
        converted = _convert_tools_to_anthropic(tools)
        assert converted == tools


# ---------------------------------------------------------------------------
# Beta header detection
# ---------------------------------------------------------------------------


class TestMinimaxEndpoint:
    def test_recognizes_minimax_io(self) -> None:
        assert _is_minimax_endpoint("https://api.minimax.io/anthropic")
        assert _is_minimax_endpoint("https://api.minimax.io/anthropic/v1")
        assert _is_minimax_endpoint("https://api.minimax.io/anthropic/")

    def test_recognizes_minimaxi_com(self) -> None:
        assert _is_minimax_endpoint("https://api.minimaxi.com/anthropic")

    def test_does_not_match_native_anthropic(self) -> None:
        assert not _is_minimax_endpoint("https://api.anthropic.com")
        assert not _is_minimax_endpoint("https://api.anthropic.com/v1")

    def test_none_base_url(self) -> None:
        assert not _is_minimax_endpoint(None)
        assert not _is_minimax_endpoint("")


class TestBuildBetaHeaders:
    def test_minimax_strips_fine_grained_tool_streaming(self) -> None:
        headers = _build_beta_headers("https://api.minimax.io/anthropic")
        for h in headers:
            assert "fine-grained-tool-streaming" not in h

    def test_native_anthropic_includes_interleaved_thinking(self) -> None:
        headers = _build_beta_headers("https://api.anthropic.com")
        assert any("interleaved" in h for h in headers)


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


class FakeEvent:
    """Mimics an Anthropic SDK content_block_delta event."""

    def __init__(self, type_: str, **attrs: Any) -> None:
        self.type = type_
        for k, v in attrs.items():
            setattr(self, k, v)


class TestStream:
    def _make_provider(self, events: list[Any]) -> AnthropicProvider:
        """Create a provider with a mocked stream that yields the given events."""
        # Mock the underlying client: messages.stream() returns a context manager
        # whose __enter__ returns an object with __iter__ and get_final_message.
        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = iter(events)
        mock_stream.get_final_message.return_value = MagicMock(
            stop_reason="end_turn",
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )
        mock_manager = MagicMock()
        mock_manager.__enter__.return_value = mock_stream
        mock_manager.__exit__.return_value = False
        mock_client = MagicMock()
        mock_client.messages.stream.return_value = mock_manager

        provider = object.__new__(AnthropicProvider)
        provider._model = "minimax/MiniMax-M3"
        provider._client = mock_client
        return provider

    def test_text_stream_yields_text_chunks(self) -> None:
        events = [
            FakeEvent("content_block_start", index=0),
            FakeEvent(
                "content_block_delta",
                index=0,
                delta=FakeEvent("text_delta", text="Hello ", type="text_delta"),
            ),
            FakeEvent(
                "content_block_delta",
                index=0,
                delta=FakeEvent("text_delta", text="world!", type="text_delta"),
            ),
            FakeEvent("message_delta", delta=MagicMock(stop_reason="end_turn")),
            FakeEvent("message_stop"),
        ]
        provider = self._make_provider(events)
        chunks = list(
            provider.stream(
                [{"role": "user", "content": "Hi"}],
                max_tokens=100,
            )
        )
        text_chunks = [c for c in chunks if c.kind == "text"]
        assert [c.content for c in text_chunks] == ["Hello ", "world!"]

    def test_reasoning_stream_yields_reasoning_chunks(self) -> None:
        events = [
            FakeEvent("content_block_start", index=0),
            FakeEvent(
                "content_block_delta",
                index=0,
                delta=FakeEvent(
                    "thinking_delta", thinking="Let me think...", type="thinking_delta"
                ),
            ),
            FakeEvent(
                "content_block_delta",
                index=0,
                delta=FakeEvent("text_delta", text="Answer!", type="text_delta"),
            ),
        ]
        provider = self._make_provider(events)
        chunks = list(provider.stream([{"role": "user", "content": "q"}], max_tokens=100))
        reasoning = [c for c in chunks if c.kind == "reasoning"]
        text = [c for c in chunks if c.kind == "text"]
        assert [c.content for c in reasoning] == ["Let me think..."]
        assert [c.content for c in text] == ["Answer!"]

    def test_tool_call_split_across_two_deltas(self) -> None:
        events = [
            FakeEvent(
                "content_block_start",
                index=0,
                content_block=type(
                    "CB",
                    (),
                    {"type": "tool_use", "id": "call_1", "name": "get_weather"},
                )(),
            ),
            FakeEvent(
                "content_block_delta",
                index=0,
                delta=FakeEvent(
                    "input_json_delta", partial_json='{"loc', type="input_json_delta"
                ),
            ),
            FakeEvent(
                "content_block_delta",
                index=0,
                delta=FakeEvent(
                    "input_json_delta", partial_json='ation": "Berlin"}', type="input_json_delta"
                ),
            ),
            FakeEvent("content_block_stop", index=0),
        ]
        provider = self._make_provider(events)
        chunks = list(provider.stream([{"role": "user", "content": "q"}], max_tokens=100))
        tool_chunks = [c for c in chunks if c.kind == "tool_call"]
        assert len(tool_chunks) == 1
        assert tool_chunks[0].tool_call.id == "call_1"
        assert tool_chunks[0].tool_call.name == "get_weather"
        assert tool_chunks[0].tool_call.arguments == {"location": "Berlin"}

    def test_done_chunk_at_end(self) -> None:
        events = [
            FakeEvent("content_block_start", index=0),
            FakeEvent("message_stop"),
        ]
        provider = self._make_provider(events)
        chunks = list(provider.stream([{"role": "user", "content": "q"}], max_tokens=100))
        assert chunks[-1].kind == "done"

    def test_messages_converted_to_anthropic_format(self) -> None:
        events = [FakeEvent("message_stop")]
        provider = self._make_provider(events)
        msgs = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "Hi"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "c1",
                        "function": {"name": "f", "arguments": {"x": 1}},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": "42"},
        ]
        list(provider.stream(msgs, max_tokens=100))
        # Inspect what we sent to the client
        call_kwargs = provider._client.messages.stream.call_args.kwargs
        assert call_kwargs["model"] == "minimax/MiniMax-M3"
        assert call_kwargs["max_tokens"] == 100
        assert call_kwargs["system"] == "System prompt."
        sent_messages = call_kwargs["messages"]
        assert sent_messages[0] == {"role": "user", "content": "Hi"}
        assert sent_messages[1]["content"][0]["type"] == "tool_use"
        assert sent_messages[1]["content"][0]["name"] == "f"
        assert sent_messages[2]["content"][0]["type"] == "tool_result"
        assert sent_messages[2]["content"][0]["tool_use_id"] == "c1"

    def test_tools_converted_to_anthropic_format(self) -> None:
        events = [FakeEvent("message_stop")]
        provider = self._make_provider(events)
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "my_tool",
                    "description": "desc",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        list(provider.stream([{"role": "user", "content": "q"}], max_tokens=100, tools=tools))
        call_kwargs = provider._client.messages.stream.call_args.kwargs
        assert call_kwargs["tools"] == [
            {
                "name": "my_tool",
                "description": "desc",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

    def test_max_tokens_passed_through(self) -> None:
        events = [FakeEvent("message_stop")]
        provider = self._make_provider(events)
        list(provider.stream([{"role": "user", "content": "q"}], max_tokens=8192))
        assert provider._client.messages.stream.call_args.kwargs["max_tokens"] == 8192

    def test_default_max_tokens_4096(self) -> None:
        events = [FakeEvent("message_stop")]
        provider = self._make_provider(events)
        list(provider.stream([{"role": "user", "content": "q"}]))
        assert provider._client.messages.stream.call_args.kwargs["max_tokens"] == 4096


class TestProviderConstruction:
    """Verify that the Anthropic SDK is used correctly at construction."""

    def test_strips_v1_suffix_from_base_url(self) -> None:
        mock_sdk = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_sdk}):
            AnthropicProvider(
                api_key="sk-test",
                base_url="https://api.minimax.io/anthropic/v1",
                model="minimax/MiniMax-M3",
            )
        kwargs = mock_sdk.Anthropic.call_args.kwargs
        assert kwargs["base_url"] == "https://api.minimax.io/anthropic"

    def test_keeps_base_url_without_v1(self) -> None:
        mock_sdk = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_sdk}):
            AnthropicProvider(
                api_key="sk-test",
                base_url="https://api.minimax.io/anthropic",
                model="minimax/MiniMax-M3",
            )
        kwargs = mock_sdk.Anthropic.call_args.kwargs
        assert kwargs["base_url"] == "https://api.minimax.io/anthropic"

    def test_native_anthropic_includes_interleaved_beta(self) -> None:
        mock_sdk = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_sdk}):
            AnthropicProvider(
                api_key="sk-ant-test",
                base_url="https://api.anthropic.com",
                model="claude-sonnet-4-5",
            )
        kwargs = mock_sdk.Anthropic.call_args.kwargs
        headers = kwargs["default_headers"]
        assert "interleaved" in headers["anthropic-beta"]

    def test_minimax_strips_fine_grained_tool_streaming(self) -> None:
        mock_sdk = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_sdk}):
            AnthropicProvider(
                api_key="sk-test",
                base_url="https://api.minimax.io/anthropic",
                model="minimax/MiniMax-M3",
            )
        kwargs = mock_sdk.Anthropic.call_args.kwargs
        headers = kwargs["default_headers"]
        assert "fine-grained-tool-streaming" not in headers["anthropic-beta"]

    def test_anthropic_sdk_client_constructed_with_correct_args(self) -> None:
        mock_sdk = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_sdk}):
            AnthropicProvider(
                api_key="sk-test",
                base_url="https://api.minimax.io/anthropic",
                model="minimax/MiniMax-M3",
                timeout=120.0,
            )
        kwargs = mock_sdk.Anthropic.call_args.kwargs
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["timeout"] == 120.0
        assert kwargs["max_retries"] == 0
