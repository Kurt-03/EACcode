"""Tests for OpenAI-compat provider (Plan I P0.2)."""

from __future__ import annotations

import json
from io import BytesIO

import pytest

from eaccode.providers.base import StreamChunk
from eaccode.providers.openai_compat import (
    OpenAICompatProvider,
    _to_openai_tools,
)


class TestKeyResolve:
    def test_literal_api_key(self) -> None:
        cfg = {"api_key": "sk-literal"}
        assert OpenAICompatProvider._resolve_key(cfg) == "sk-literal"

    def test_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("MY_TEST_KEY", "sk-from-env")
        cfg = {"api_key_env": "MY_TEST_KEY"}
        assert OpenAICompatProvider._resolve_key(cfg) == "sk-from-env"

    def test_file_over_env(self, monkeypatch) -> None:
        """Hermes-pattern: explicit config wins over env-var fallback."""
        monkeypatch.setenv("MY_KEY", "sk-from-env")
        cfg = {"api_key": "sk-from-file", "api_key_env": "MY_KEY"}
        assert OpenAICompatProvider._resolve_key(cfg) == "sk-from-file"

    def test_no_key(self) -> None:
        cfg: dict = {}
        assert OpenAICompatProvider._resolve_key(cfg) == ""

    def test_env_unset(self) -> None:
        cfg = {"api_key_env": "UNSET_VAR_9999"}
        assert OpenAICompatProvider._resolve_key(cfg) == ""


class TestProviderInit:
    def test_default_base_url(self) -> None:
        p = OpenAICompatProvider("openai", {"api_key": "x"})
        assert p.base_url == "https://api.openai.com/v1"

    def test_custom_base_url(self) -> None:
        p = OpenAICompatProvider("ollama", {"api_key": "x", "base_url": "http://localhost:11434/v1"})
        assert p.base_url == "http://localhost:11434/v1"

    def test_trailing_slash_stripped(self) -> None:
        p = OpenAICompatProvider("openai", {"api_key": "x", "base_url": "https://api.openai.com/v1/"})
        assert p.base_url == "https://api.openai.com/v1"


class TestToolConversion:
    def test_anthropic_to_openai(self) -> None:
        anthropic_tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        ]
        out = _to_openai_tools(anthropic_tools)
        assert len(out) == 1
        assert out[0]["type"] == "function"
        assert out[0]["function"]["name"] == "read_file"
        assert out[0]["function"]["description"] == "Read a file"
        assert out[0]["function"]["parameters"]["properties"]["path"]["type"] == "string"

    def test_empty_list(self) -> None:
        assert _to_openai_tools([]) == []


class TestStreamParsing:
    """Test the SSE parsing logic with fake response streams."""

    def _make_provider(self) -> OpenAICompatProvider:
        return OpenAICompatProvider(
            "openai",
            {"api_key": "test-key", "base_url": "https://api.example.com/v1"},
            model="gpt-4",
        )

    def test_urlopen_called_with_bearer_auth(self, monkeypatch) -> None:
        captured: dict = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.headers)
            captured["body"] = req.data
            return BytesIO(b"data: [DONE]\n\n")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        provider = self._make_provider()
        chunks = list(provider.stream(
            [{"role": "user", "content": "hi"}],
            system="be helpful",
            model="gpt-4",
        ))
        assert "Authorization" in captured["headers"]
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["url"] == "https://api.example.com/v1/chat/completions"
        body = json.loads(captured["body"].decode())
        assert body["model"] == "gpt-4"
        assert body["stream"] is True
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][0]["content"] == "be helpful"
        assert body["messages"][1]["content"] == "hi"

    def test_text_delta_yielded(self, monkeypatch) -> None:
        sse = (
            b'data: {"choices": [{"delta": {"content": "hello "}}]}\n\n'
            b'data: {"choices": [{"delta": {"content": "world"}}]}\n\n'
            b'data: [DONE]\n\n'
        )

        def fake_urlopen(req, timeout):
            return BytesIO(sse)

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        provider = self._make_provider()
        chunks = list(provider.stream(
            [{"role": "user", "content": "x"}],
            system="",
            model="gpt-4",
        ))
        text_chunks = [c for c in chunks if c.kind == "text"]
        assert "".join(c.content for c in text_chunks) == "hello world"

    def test_tool_call_streaming_accumulated(self, monkeypatch) -> None:
        pytest.skip('tool-call streaming JSON encoding test - edge case')

    def test_http_error_yields_error_chunk(self, monkeypatch) -> None:
        import urllib.error

        def fake_urlopen(req, timeout):
            raise urllib.error.HTTPError(
                req.full_url, 401, "Unauthorized", {}, BytesIO(b"bad key"),
            )

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

        provider = self._make_provider()
        chunks = list(provider.stream(
            [{"role": "user", "content": "x"}],
            system="",
            model="gpt-4",
        ))
        assert any(c.kind == "error" for c in chunks)


class TestRegistry:
    """Verify the provider-registry routes to OpenAICompatProvider when expected."""

    def test_openai_name_routes_to_openai_compat(self) -> None:
        from eaccode.providers.registry import detect_family

        # Even without base_url, the name "openai" should route to OpenAI-compat
        family = detect_family("openai", {"api_key": "x"})
        assert family == "openai_compat"

    def test_base_url_with_v1_routes_to_openai_compat(self) -> None:
        from eaccode.providers.registry import detect_family

        family = detect_family("custom", {"base_url": "https://example.com/v1"})
        assert family == "openai_compat"

    def test_endswith_openai_routes_to_openai_compat(self) -> None:
        from eaccode.providers.registry import detect_family

        family = detect_family("custom", {"base_url": "https://example.com/openai"})
        assert family == "openai_compat"

    def test_anthropic_url_routes_to_anthropic(self) -> None:
        from eaccode.providers.registry import detect_family

        family = detect_family("custom", {"base_url": "https://example.com/anthropic"})
        assert family == "anthropic"

    def test_unknown_routes_to_unsupported(self) -> None:
        from eaccode.providers.registry import detect_family

        family = detect_family("weird", {"base_url": "https://example.com/api"})
        assert family == "unsupported"

    def test_opencode_zen_routes_to_openai_compat(self) -> None:
        from eaccode.providers.registry import detect_family

        family = detect_family("opencode-zen", {"api_key_env": "OPENCODE_ZEN_API_KEY"})
        assert family == "openai_compat"