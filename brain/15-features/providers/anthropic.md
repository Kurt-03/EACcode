---
name: anthropic-provider
type: provider
status: done
phase: 08-17 anthropic-sdk
date: 2026-08-17
tags: [type/feature, feature/provider, anthropic, hermes]
---

# Provider: Anthropic Messages API

> Official Anthropic-SDK, gegen jeden `/anthropic`-Endpunkt — nativ oder
> kompatibel (MiniMax).

## Zweck

Seit 08-17 (Plan) ist eaccode auf **Anthropic-SDK direkt** umgestiegen
(raus aus LiteLLM). Der Adapter normalisiert sowohl das native Anthropic-
Console-Format (`api.anthropic.com`) als auch MiniMax' Anthropic-kompatiblen
Endpoint (`api.minimax.io/anthropic`, Bearer-auth) auf ein gemeinsames
StreamChunk-Format.

## Stream-Normalisierung

- `text_delta` → `StreamChunk(kind="text", content=...)`
- `thinking_delta` → `StreamChunk(kind="reasoning", content=...)`
- `content_block_start` mit `input_json_delta` → `StreamChunk(kind="tool_call", tool_call=partial)`
- `message_delta` mit `stop_reason` → `StreamChunk(kind="done", stop_reason=...)`
- Token-Counts am Stream-Ende → `StreamChunk(kind="usage", usage={...})`

Tool-Calls werden über mehrere Chunks akkumuliert (id + name + arguments).

## Beta-Header-Anpassungen

```python
_MINIMAX_BETA_HEADERS_TO_STRIP = {"fine-grained-tool-streaming-2025-05-14"}
```

`_build_beta_headers(base_url)` strippt automatisch Header, die MiniMax'
Anthropic-compat-Endpoint ablehnt. Native Anthropic-Console bekommt:
`["interleaved-thinking-2025-05-14"]`.

## Auth-Schema

- Native Anthropic: `x-api-key: <KEY>`
- MiniMax-Anthropic: `Authorization: Bearer <KEY>`

Detektion via `_is_minimax_endpoint(base_url)`.

## Verknüpft
- [[15-features/providers/registry.md|registry]]
- [[15-features/system/providers.md|providers]]
- [[15-features/system/model-router.md|Model Router]]
- ADR: [[ADR/0004-litellm-to-anthropic-sdk.md|0004-litellm-to-anthropic-sdk]]
