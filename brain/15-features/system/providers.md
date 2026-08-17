---
title: Provider Architecture (Anthropic-Messages Compatible)
description: Stable Provider protocol + StreamChunk dataclass. Anthropic SDK adapter for MiniMax (Anthropic-compatible mode). Lazy registration via URL-based family detection.
tags: [system, providers, anthropic, streaming, sdk]
created: 2026-08-17
updated: 2026-08-17
---

# Provider Architecture

**Modul:** `src/eaccode/providers/`
**Public API:** `from eaccode.providers import registry as providers`
**Anthropic-SDK:** `anthropic==0.87.0`
**Hermes-Referenz:** `C:/Projekte/_ref/hermes/agent/anthropic_adapter.py`

## Zweck

eaccode ist ein BYOK-Agent mit **mehreren Modell-Providern**. Bis 2026-08-17 lief das Ganze durch **LiteLLM** — was sich als problematisch herausstellte:

1. LiteLLM normalisiert MiniMax-Anthropic-Streams zu OpenAI-Format
2. LiteLLM verliert dabei `reasoning_content`-Reihenfolge
3. LiteLLM schickt die falschen Auth-Header (x-api-key statt Bearer)
4. LiteLLM schickt Beta-Header, die MiniMax ablehnt

Daher: **direkter Anthropic SDK** (für Anthropic-kompatible Provider) + **StreamChunk-Normalisierung** für den Agent.

## Architektur

```
┌─────────────────────────────────────────────────────────┐
│ Agent (eaccode.agent.Agent)                             │
│   ├─ _complete() iterates StreamChunk from stream()    │
│   └─ baut tool_call/content/reasoning aus Chunks       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Provider Registry (eaccode.providers.registry)          │
│   ├─ detect_family(provider_name, config) -> kind      │
│   ├─ get(provider_name, config, model=...) -> Provider  │
│   └─ Cache per (provider, base_url, api_key)           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ AnthropicProvider (eaccode.providers.anthropic)         │
│   ├─ stream(messages, ...) → Iterator[StreamChunk]      │
│   ├─ Normalisiert content/events → StreamChunk          │
│   └─ Anthropic Messages API (auch MiniMax kompatibel)   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                https://api.minimax.io/anthropic/v1/messages
```

## StreamChunk — das Normalisierte Format

```python
@dataclass
class StreamChunk:
    kind: str                       # "text", "reasoning", "tool_call", "usage", "done"
    content: str = ""               # text content
    tool_call: ToolCall | None      # bei kind="tool_call"
    usage: dict[str, int] = {}      # bei kind="usage"
    stop_reason: str = ""           # bei kind="done"
```

**Wichtig:** Der Agent sieht **nie** Anthropic-Events. Nur `StreamChunk`. Jeder Adapter konvertiert nativ → StreamChunk.

## Implementierter Adapter

Nur **Anthropic-Messages-kompatibel**:

| Provider | Status | Basis |
|----------|--------|-------|
| MiniMax (Alle 7 Modelle) | ✅ funktional | `https://api.minimax.io/anthropic/v1` |
| Anthropic (Native) | ✅ funktional | `https://api.anthropic.com/v1` |
| OpenAI | ❌ not implemented | out of scope |
| Ollama | ❌ not implemented | rausgenommen |
| Azure | ❌ not implemented | out of scope |

**MiniMax-spezifische Anpassungen:**

- **Beta-Header `interleaved-thinking-2025-05-14`** wird mitgeschickt
- **Beta-Header `fine-grained-tool-streaming-2025-05-14`** wird NICHT mitgeschickt (MiniMax lehnt den ab)
- **Base-URL `/v1`-Suffix** wird automatisch gestrippt (SDK appendet ihn selbst)
- **Standard `max_tokens=4096`** als Default im Adapter (sonst empty choices[])

## Family Detection

```python
def detect_family(provider_name, provider_config) -> str:
    base_url = (provider_config.get("base_url") or "").rstrip("/").lower()
    if base_url.endswith("/anthropic"):
        return "anthropic"
    if provider_name in {"anthropic", "minimax", "minimax-oauth", "minimax-cn"}:
        return "anthropic"
    return "unsupported"
```

**Zwei Wege:** Entweder expliziter `base_url` der auf `/anthropic` endet, oder ein bekannter Provider-Name. Wenn keiner — `NotImplementedError`.

## Cache

```python
_provider_cache: dict[tuple[str, str, str], Provider] = {}
# Cache-Key: (provider_name, base_url, api_key)
```

`Provider.stream()` ist **stateful** (es hält den SDK-Client). Daher pro (provider, base_url, api_key) **eine Instanz** — die reuseable ist.

## Tool-Grenzen

Anthropic hat **ein Tool-Use-Block** pro Stream, der über mehrere `content_block_delta` Events **verteilt** wird. Der Adapter **akkumuliert** `input_json_delta` über Chunks und emit **ein** `StreamChunk(kind="tool_call")` beim `content_block_stop`.

## Tests

**`tests/test_providers_anthropic.py`** — 27 Tests:
- Message-Konvertierung (System, Tool-Calls, Tool-Result)
- Tool-Schema-Konvertierung (OpenAI → Anthropic)
- Beta-Header (MiniMax strip, Anthropic keep)
- Stream-Konvertierung (text, reasoning, tool_call)
- Tool-Call-Splitting-across-chunks
- Provider-Construction (base_url, vs1, beta)

**`tests/test_providers_registry.py`** — 16 Tests:
- Family detection (URL, name)
- API-Key (env > file)
- Registry get (Anthropic returns, unknown raises)
- Cache (same key, different key)

## Lessons

- **Lazy Anthropic-Import:** `import anthropic` nur in `__init__`, NICHT auf Module-Level. Tests, die den SDK nicht brauchen, laufen sonst mit 220ms Cold-Start-Schaden.
- **Patch.dict für sys.modules:** `with patch("eaccode.providers.anthropic.anthropic")` crashed mit `AttributeError`, weil `anthropic` kein Modul-Attribut ist. Workaround: `patch.dict("sys.modules", {"anthropic": mock_sdk})`.
- **Test-Isolation via tmp_path:** Reset-Fixture redirected `_get_cache_path()` to `tmp_path`, sonst leaken Tests in den User-Cache.

## Verwandt

- `brain/15-features/system/models-dev.md` — Models.dev als Catalog
- `brain/15-features/system/model-router.md` — der **frühere** LiteLLM-Router (deprecated)
- `brain/15-features/system/agent.md` — Agent-Loop mit StreamChunk
- Hermes-Adapter: `C:/Projekte/_ref/hermes/agent/anthropic_adapter.py`
- Commit-Log: `f0003d5` (init), `66aeab6` (registry)
