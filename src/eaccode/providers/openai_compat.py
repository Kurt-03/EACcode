"""OpenAI-compatible provider adapter (Plan I P0.2).

Implements the ``/v1/chat/completions`` streaming protocol used by:
- OpenAI
- OpenRouter
- Ollama (``/v1`` prefix)
- vLLM
- DeepSeek
- Groq
- xAI (Grok)
- OpenCode Zen
- Any other provider that speaks the OpenAI Chat Completions schema

This is **not** a fork of the Anthropic adapter - it's a sibling
implementation that lives next to it. URL-family detection
(``endswith("/openai")`` or ``contains("/v1")``) routes here.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from typing import Any, Iterator

from eaccode.providers.base import Provider, StreamChunk, ToolCall


class OpenAICompatProvider(Provider):
    """OpenAI-compatible chat-completions adapter."""

    def __init__(
        self,
        name: str,
        config: dict[str, Any],
        model: str | None = None,
    ) -> None:
        super().__init__(name, config, model)
        self.base_url = (config.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = self._resolve_key(config)
        self.timeout = float(config.get("timeout", 60.0))

    @staticmethod
    def _resolve_key(config: dict[str, Any]) -> str:
        """Pick the API key from ``api_key`` (literal) or env-var ``api_key_env``."""
        key = config.get("api_key")
        if key:
            return key
        env_name = config.get("api_key_env")
        if env_name:
            return os.environ.get(env_name, "")
        return ""

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str = "",
        model: str,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> Iterator[StreamChunk]:
        """Stream a chat completion from the OpenAI-compatible endpoint."""
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        # OpenAI chat-completions: system goes in messages[0] with role=system
        out_messages: list[dict[str, Any]] = []
        if system:
            out_messages.append({"role": "system", "content": system})
        out_messages.extend(messages)
        payload["messages"] = out_messages
        if tools:
            payload["tools"] = _to_openai_tools(tools)

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            yield StreamChunk(kind="error", content=f"HTTP {exc.code}: {detail}")
            return
        except urllib.error.URLError as exc:
            yield StreamChunk(kind="error", content=f"connection failed: {exc.reason}")
            return

        # Stream SSE lines.
        tool_call_acc: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                evt = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = evt.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta", {})

            # Content
            content = delta.get("content")
            if content:
                yield StreamChunk(kind="text", content=content)

            # Tool calls (OpenAI streams them as delta updates)
            for tc_delta in delta.get("tool_calls") or []:
                idx = tc_delta.get("index", 0)
                if idx not in tool_call_acc:
                    tool_call_acc[idx] = {
                        "id": tc_delta.get("id", ""),
                        "name": "",
                        "arguments": "",
                    }
                acc = tool_call_acc[idx]
                fn = tc_delta.get("function") or {}
                if fn.get("name"):
                    acc["name"] = fn["name"]
                if fn.get("arguments"):
                    acc["arguments"] += fn["arguments"]

            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

        # Emit accumulated tool calls
        for tc in tool_call_acc.values():
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {"_raw": tc["arguments"]}
            yield StreamChunk(
                kind="tool_call",
                tool_call=ToolCall(
                    id=tc["id"] or "",
                    name=tc["name"],
                    arguments=args,
                ),
            )

        yield StreamChunk(kind="done", stop_reason=finish_reason)

    async def stream_async(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str = "",
        model: str,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[StreamChunk]:
        """Async variant of stream(): uses httpx.AsyncClient + aiter_lines."""
        import httpx
        import json as _json

        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        out_messages: list[dict[str, Any]] = []
        if system:
            out_messages.append({"role": "system", "content": system})
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "tool":
                out_messages.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", ""),
                    "content": content,
                })
            elif role == "assistant" and m.get("tool_calls"):
                tc_payload = []
                for tc in m["tool_calls"]:
                    tc_payload.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    })
                out_messages.append({
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": tc_payload,
                })
            else:
                out_messages.append({"role": role, "content": content})
        payload["messages"] = out_messages
        if tools:
            payload["tools"] = _to_openai_tools(tools)

        headers = {
            "Authorization": f"Bearer {self._resolve_key(self.config)}",
            "Content-Type": "application/json",
        }

        pending_tool_calls: dict[int, dict[str, Any]] = {}
        finish_reason = ""

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = line[len("data: "):]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            obj = _json.loads(data)
                        except _json.JSONDecodeError:
                            continue
                        choices = obj.get("choices", [])
                        if not choices:
                            continue
                        ch = choices[0]
                        finish_reason = ch.get("finish_reason", finish_reason) or finish_reason
                        delta = ch.get("delta", {})
                        text = delta.get("content") or ""
                        if text:
                            yield StreamChunk(kind="text", content=text)
                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            if idx not in pending_tool_calls:
                                pending_tool_calls[idx] = {
                                    "id": tc.get("id", "") or "",
                                    "name": (tc.get("function") or {}).get("name", "") or "",
                                    "arguments": "",
                                }
                            if tc.get("id"):
                                pending_tool_calls[idx]["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                pending_tool_calls[idx]["name"] = fn["name"]
                            if fn.get("arguments"):
                                pending_tool_calls[idx]["arguments"] += fn["arguments"]

            # Flush pending tool calls
            for _idx, tc in pending_tool_calls.items():
                import json as _json
                try:
                    args = _json.loads(tc["arguments"] or "{}")
                except _json.JSONDecodeError:
                    args = {}
                yield StreamChunk(
                    kind="tool_call",
                    tool_call=ToolCall(
                        id=tc["id"] or "",
                        name=tc["name"],
                        arguments=args,
                    ),
                )
        yield StreamChunk(kind="done", stop_reason=finish_reason or "end_turn")


def _to_openai_tools(anthropic_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic tool schemas to OpenAI ``tools`` format.

    Anthropic format:
        ``{"name": ..., "description": ..., "input_schema": {...}}``

    OpenAI format:
        ``{"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}``
    """
    out: list[dict[str, Any]] = []
    for tool in anthropic_tools:
        out.append({
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return out