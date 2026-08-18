---
name: providers-base
type: system
status: done
phase: 08-17 anthropic-sdk
date: 2026-08-17
tags: [type/feature, feature/system, hermes]
---

# Providers — Base Types (Stream-Normalisierung)

> `StreamChunk` und `ToolCall` definieren die provider-neutrale Wire-Format-
> Zwischenebene. Jede Adapter-Implementierung mappt ihre native SDK-Welt
> darauf.

## Datenmodell

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict   # akkumuliert über mehrere Chunks

@dataclass
class StreamChunk:
    kind: Literal["text", "reasoning", "tool_call", "usage", "done"]
    content: str = ""
    tool_call: ToolCall | None = None
    usage: dict = field(default_factory=dict)   # input_tokens, output_tokens
    stop_reason: str = ""
```

Jeder Adapter streamt genau diese Chunks. Der Agent-Layer sieht nur
StreamChunk — keine Anthropic/OpenAI-Typen.

## Provider-Protocol

```python
class Provider(Protocol):
    def stream(messages, *, system, tools, max_tokens, temperature,
               cancel_event, extra) -> Iterator[StreamChunk]: ...
    def complete(messages, **kwargs) -> StreamChunk   # optional
```

`cancel_event` (Optional `threading.Event`) wird respektiert: nächster
Chunk-Check wirft `OperationCancelled`.

## Verknüpft

- [[15-features/providers/anthropic.md|anthropic]]
- [[15-features/providers/registry.md|registry]]
- [[15-features/system/providers.md|providers]]
