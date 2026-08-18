---
name: denial-breaker
type: system
status: done
phase: 08-18 plan-g-v5-g11-plan-c
date: 2026-08-18
tags: [type/feature, feature/system, permissions, hermes]
---

# Denial Breaker — Circuit Breaker for Aux-LLM Denials (G.11)

> Wenn die Aux-LLM N-mal hintereinander DENY sagt, wird der nächste Call
> blockiert ohne erneute Aux-LLM-Konsultation. Reset bei User-Approve.

## Konfiguration

```python
DenialBreaker(threshold: int = 3, max_sessions: int = 256)
```

## Verhalten

- `record(session_key)` → incremented tally, returns new count
- Nach `threshold` aufeinanderfolgenden Denials → next call blockiert
- `reset(session_key)` → tally gelöscht (User hat approven)
- LRU eviction ab `max_sessions` (älteste Session-Key raus)

## API

```python
class DenialBreaker:
    def record(session_key) -> int       # return new count
    def reset(session_key) -> None
    def is_open(session_key) -> bool     # threshold überschritten?
    def snapshot() -> dict               # für Debug-Ausgabe
    def set_threshold(t) -> None
    @property threshold
```

Singleton: `denial_breaker.get_instance()` (lazy in `permissions.py`).

## Wire-Position

In `permissions.py:check()`, nach Aux-LLM-Verdict == DENY:

```python
if breaker.record(session_key) >= breaker.threshold:
    return Decision(scope="deny_always", reason="denial-breaker")
```

User-Approve (egal welcher scope) → `breaker.reset(session_key)`.

## Hermes-Vergleich

Hermes `_record_denial / _reset_denials / _denial_breaker_addendum`. Wir haben
alle drei Logik-Pfade in `class DenialBreaker` zusammengefasst — gleicher
Effekt, kompakter.

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.11
- [[15-features/system/permissions.md|permissions]]
- [[15-features/system/smart-approval.md|smart-approval]]
- Hermes source: `_ref/hermes/approval.py`

## Tests

`tests/test_denial_breaker.py` — Threshold-Trip, Reset, LRU-eviction, thread-safety.
