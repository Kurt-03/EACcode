---
name: tool-result-storage
type: system
status: done
phase: 08-18 plan-g-v5-g3
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# Tool Result Storage — 3-Layer Context-Overflow Defense (G.3)

> Wenn ein einzelnes Tool-Result den Context sprengt, spillt eaccode auf Disk
> und ersetzt den In-Context-Inhalt durch Preview + Pfad.

## Schichten

| Layer | Wo | Wann |
|---|---|---|
| **1. Per-Tool Cap** | Im Tool selbst (`max_chars`-Default) | Vor Return |
| **2. Per-Result Persistence** | Disk unter `<data>/tool-results/<id>.txt` | Wenn Cap überschritten |
| **3. Per-Turn Aggregate** | Nach Collect aller Results im Turn | Wenn `MAX_TURN_BUDGET_CHARS = 200_000` überschritten |

Layer 2 + 3 schreiben nach `<persisted-output>...</persisted-output>`-Tags;
das Modell kann via `read_file(path)` nachladen.

## Public API

```python
PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"
MAX_PREVIEW_CHARS = 800
MAX_TURN_BUDGET_CHARS = 200_000

def maybe_persist(tool_call_id, body) -> dict
    # Returns the in-context body (truncated if persisted)
def spill_excess(results, budget) -> list
    # Aggregat-Layer: spillt Largest-first bis budget erfüllt
```

## Integration

`agent.py:run()` ruft `maybe_persist` zwischen Tool-Return und Modellen-Response.
Nach dem finalen Tool des Turns: `spill_excess` aggregiert.

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.3
- Hermes source: `tools/tool_result_storage.py` + `tools/hook_output_spill.py`

## Tests

`tests/test_tool_result_storage.py` — Layer 1+2+3 happy-path, Persistence-Marker,
Aggregate-Layer mit multiple-results budget-stress.
