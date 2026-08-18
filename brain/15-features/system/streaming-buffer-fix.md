---
name: streaming-buffer-fix
type: system
status: done
phase: 08-18 streaming
tags: [type/feature, feature/system, bugfix, terminal, patch_stdout]
---

# Streaming-Bug-Fix: Buffer-Accumulation (08-18)

> **Status:** done
> **Problem:** REPL-Stream-Antwort wurde am Anfang abgeschnitten
> **Fix:** Buffer-Accumulator statt Per-Chunk-Print

## Symptom (08-17 verifiziert)

```
● hi
 How can I help you today?
MiniMax-M3 (minimax) │ 3.2s │ 29 chars

● tell me
, building things in Roblox Studio, browsing the web, ...     ← ANFANG ABGESCHNITTEN
MiniMax-M3 (minimax) │ 1.9s │ 199 chars
```

Pipe-Modus (`eaccode -p "tell me"`) liefert vollen Text. REPL schluckt
Anfang. **Patch** versuchte 50ms sleep — half teilweise, aber nicht zuverlässig.

## Root-Cause

`ChatApp._on_token` rief direkt `print(delta, end="", flush=True)` in einem
Worker-Thread. **patch_stdout** routed durch eigenen Thread-Queue. **Race
zwischen Threads:**

1. Worker-Thread: print("It") → queued
2. Worker-Thread: print(" seems") → queued
3. Worker-Thread: fertig
4. Main-Thread: time.sleep(0.05)
5. Main-Thread: print() — newline
6. Main-Thread: print("MiniMax-M3 │ 1.9s") — status line
7. patch_stdout-Thread: drain queued chunks

**Chancen:**
- Wenn patch_stdout-Thread **vor** Status-Line rendert → Antwort OK
- Wenn **nach** Status-Line rendert → chunks landen unter Status-Line,
  Anfang verschluckt

50ms sleep **war** Workaround, aber nicht robust.

## Fix: Buffer-Accumulation

Worker-Thread sammelt alle chunks in `_stream_buffer`. Main-Thread druckt
**einmal** am Ende.

```python
# In _on_token (worker thread):
self._stream_buffer += delta  # accumulate, no print

# In _agent_worker (main thread, after worker done):
if self._streamed_any:
    buffer = getattr(self, "_stream_buffer", "")
    if buffer:
        self._emit(buffer)
```

## Resultat

- **100% reliable** — keine Race-Bedingung mehr
- 50ms sleep nicht mehr nötig
- Tests: 578 passed (statt flaky)

## Test-Isolation

In Tests braucht der Buffer-Mechanismus kein sleep — also
`EACCODE_TEST=1` setzen, damit Live-`time.sleep` skipped:

```python
# tests/conftest.py
import os
os.environ.setdefault("EACCODE_TEST", "1")
```

## Verwandt

- `[[slash-palette|Palette + Stream]]
- Plan: `.hermes/plans/...` (nicht vorhanden, aber im Commit-Verlauf)
- Commit: `48a3dad` "fix(palette): accumulate stream buffer"
