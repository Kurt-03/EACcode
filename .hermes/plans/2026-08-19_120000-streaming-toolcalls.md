# Plan K: Echt-Streaming + Volle Tool-Call-Darstellung

> **Fokus:** Token-by-Token Output im TUI/CLI + sichtbare Tool-Aufrufe mit Args, Result, Timing
> **Hermes-Pattern:** `StreamChunk` mit `tool_start` / `tool_end` / `tool_error` events; TUI zeigt collapsible sections

## Was wir heute haben (Audit)

| Feature | Status |
|---|---|
| Model-Stream (Text-Tokens) | ⚠️ Callback existiert (`on_token`), wird aber im CLI nicht genutzt — Buffer-Akkumulation, Output am Ende |
| Tool-Call-Stream | ❌ Komplett unsichtbar — wird im `_complete()`-Loop in dict akkumuliert, keine Events nach außen |
| Tool-Args-Anzeige | ❌ Keine |
| Tool-Result-Anzeige | ❌ Keine |
| Tool-Timing | ❌ Keine |
| Tool-Error-Anzeige | ⚠️ `return f"Error: ..."` in message, aber nicht als separates Event |
| Sub-Agent-Nesting | ❌ Keine |
| TUI-Collapsibles | ❌ Keine — Textual zeigt nur finalen Text |

## Was wir brauchen (Hermes-Verbatim)

### Phase 1 — `StreamChunk` erweitern (~150 LOC)

`src/eaccode/providers/base.py` + alle Provider:

```python
@dataclass
class StreamChunk:
    kind: str  # text | reasoning | tool_call | tool_start | tool_end | tool_error | done | error
    content: str | None = None
    tool_call: ToolCall | None = None
    tool_name: str | None = None        # NEW: for tool_start/tool_end
    tool_args: dict | None = None        # NEW: short preview of args
    tool_result: str | None = None       # NEW: short preview of result
    tool_duration_ms: int | None = None  # NEW: timing
    tool_error: str | None = None        # NEW: error message
    usage: dict | None = None
    stop_reason: str | None = None
```

Provider-emit:
- **Anthropic**: `content_block_start` (tool_use) → `tool_start`. `content_block_stop` → after tool executes → `tool_end`.
- **OpenAI-compat**: Same model.
- **Stop-reason `tool_use`** → `tool_start`. After `_execute_tool` returns → `tool_end`.

### Phase 2 — Agent-Loop instrumentieren (~200 LOC)

`src/eaccode/agent.py` `_complete()` + `run()`:

```python
for chunk in provider.stream(...):
    if chunk.kind == "tool_call":
        # Emit tool_start BEFORE the tool actually runs
        yield StreamChunk(
            kind="tool_start",
            tool_name=chunk.tool_call.name,
            tool_args=_shorten_args(chunk.tool_call.arguments, max_len=80),
        )
        # Store tool_call for later execution
    
    # ... after tool execution:
    yield StreamChunk(
        kind="tool_end",
        tool_name=tool_name,
        tool_result=_shorten(result, max_len=200),
        tool_duration_ms=int((time.monotonic() - start) * 1000),
    )
```

### Phase 3 — CLI Renderer (~150 LOC)

`src/eaccode/cli.py` + neuer `src/eaccode/render.py`:

```python
def render_stream(chunk: StreamChunk) -> str | None:
    """Format a stream chunk for terminal output. None = no output."""
    if chunk.kind == "text":
        return chunk.content
    if chunk.kind == "tool_start":
        return f"  🔧 {chunk.tool_name}({_short(chunk.tool_args)})\n"
    if chunk.kind == "tool_end":
        return f"  ✓ {chunk.tool_name} ({chunk.tool_duration_ms}ms): {_short(chunk.tool_result)}\n"
    if chunk.kind == "tool_error":
        return f"  ✗ {chunk.tool_name}: {chunk.tool_error}\n"
    return None
```

Mit `--verbose` flag kann User entscheiden ob er die Tool-Calls sehen will.

### Phase 4 — TUI Collapsibles (~250 LOC)

`src/eaccode/palette.py` — neue `_tool_section_widget`:

```python
class ToolCallSection(Collapsible):
    """Collapsible section showing one tool call + result."""
    
    def __init__(self, name: str, args: dict, result: str, duration_ms: int, error: str | None):
        title = f"🔧 {name}({_short(args)}) — {duration_ms}ms"
        super().__init__(title=title, collapsed=False)
        if error:
            self._render_error(error)
        else:
            self._render_result(_short(result, 200))
        # Button to expand full result
```

In `App.run()`:
- Hook `on_chunk` callback
- Detect `tool_start` → push new `ToolCallSection` into a log container
- Detect `tool_end`/`tool_error` → update the latest section's state

### Phase 5 — Sub-Agent-Nesting (~150 LOC)

`src/eaccode/subagents.py` — recursive emission:

```python
def spawn_subagent(...):
    # Pre-emit
    yield StreamChunk(kind="tool_start", tool_name="spawn_subagent", tool_args={...})
    # Run subagent
    for inner_chunk in sub_agent_stream:
        # Re-emit with subagent marker
        yield StreamChunk(
            kind=inner_chunk.kind,
            content=inner_chunk.content,
            sub_agent_id=id(self),
            sub_agent_task=task[:60],
        )
    yield StreamChunk(kind="tool_end", tool_name="spawn_subagent", ...)
```

TUI shows sub-agent tools as nested Collapsibles with ↳ prefix.

### Phase 6 — Secret-Redaction + Args-Truncation (~100 LOC)

`src/eaccode/render.py` — `_shorten_args()`:

```python
SECRET_KEYS = {"api_key", "password", "secret", "token"}

def _shorten_args(args: dict, max_len: int = 80) -> str:
    safe = {}
    for k, v in args.items():
        if k.lower() in SECRET_KEYS:
            safe[k] = "***REDACTED***"
        else:
            s = str(v)
            safe[k] = s[:max_len] + "..." if len(s) > max_len else s
    return ", ".join(f"{k}={v!r}" for k, v in safe.items())
```

## Was wir **nicht** machen

- **Volle Re-Streaming-Engine-Replace**: Risiko zu hoch, würde 2 Wochen dauern
- **Animationen** (spinner, transitions): Hermes hat's, aber nice-to-have
- **Tool-Permission-Diff vor Call**: nicht teil von Streaming-Phase

## 5 Commits, ~1000 LOC, ~30 Tests

| Phase | Inhalt | LOC | Tests |
|---|---|---|---|
| **K.1** | StreamChunk-Erweiterung (tool_start/tool_end/tool_error) | 150 | 8 |
| **K.2** | Agent-Loop instrumentiert (yield tool-events) | 200 | 6 |
| **K.3** | CLI-Renderer mit --verbose flag | 150 | 8 |
| **K.4** | TUI-Collapsibles (Textual) | 250 | 5 |
| **K.5** | Sub-Agent-Nesting + Secret-Redaction | 250 | 3 |
| **Total** | | **~1000** | **~30** |

## Reihenfolge (5 Tage)

```
Tag 1: K.1 (StreamChunk) + K.2 (Agent-Loop)
Tag 2: K.3 (CLI-Renderer) — first user-visible win
Tag 3: K.4 (TUI-Collapsibles)
Tag 4: K.5 (Sub-Agent + Redaction)
Tag 5: Tests + Doku + Manual-Test
```

## Verifikation pro Phase

**K.1:**
```python
# Test: every tool execution emits tool_start + tool_end chunks
def test_tool_events_emitted():
    agent = Agent(...)
    chunks = list(agent.run_stream([...]))
    assert any(c.kind == "tool_start" for c in chunks)
    assert any(c.kind == "tool_end" for c in chunks)
```

**K.2:**
```python
# Test: order is text → tool_start → tool_end → text
def test_chunk_order():
    chunks = list(agent.run_stream([user_msg_with_tool]))
    for c in chunks:
        if c.kind == "tool_start":
            tool_name = c.tool_name
            next_chunks = chunks[idx+1:]
            assert any(c2.kind == "tool_end" and c2.tool_name == tool_name for c2 in next_chunks)
```

**K.3:**
```bash
$ eaccode --verbose -p "list src/"
# Stream live: every tool-call prints inline
🔧 list_files(path="src/") — 0.1s
  [alpha.txt, beta.md, ...]
```

**K.4:**
```
TUI shows collapsible sections per tool call.
Click to expand full result.
Sub-agent tools appear with ↳ prefix.
```

**K.5:**
```python
def test_api_key_redacted():
    args = {"api_key": "sk-secret-1234", "path": "x.py"}
    out = _shorten_args(args)
    assert "sk-secret-1234" not in out
    assert "REDACTED" in out
```

## Frage an User

**Soll ich loslegen?** Falls ja, was ist wichtiger:
- **(A)** Erst CLI-Renderer (K.1+K.2+K.3) — schnellster User-Win
- **(B)** Erst TUI-Collapsibles (K.1+K.2+K.4) — volle UX
- **(C)** Alles zusammen (5 Tage)

Sag was.