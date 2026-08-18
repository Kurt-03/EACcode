# Reasoning-Effort + Thinking-Param aktivieren — Plan

> **Status:** `DRAFT` — wartet auf User-Freigabe. Nicht ausführen.
> **Auslöser:** Hermes Desktop hat ein Model-Settings-Panel mit **Thinking** Toggle + **Effort** (siehe Screenshot 08-18). Mein eaccode sendet aktuell **keinen** `thinking.type="enabled"` + `budget_tokens` Param, darum kein `thinking_delta`-Stream.
> **Quelle:** `C:/Projekte/_ref/hermes/agent/anthropic_adapter.py` Z. 2262-2278 (THINKING_BUDGET + Mapping).

## Diagnose (warum jetzt sichtbar)

**VORHERIGE Annahme (08-17):** "MiniMax-M3 sendet Reasoning inline im text_delta" — **FALSCH**, korrigiert 08-18.

**WAHR:** MiniMax-M3 sendet **gar kein** Reasoning weil:
- Mein `AnthropicProvider` setzt nur den `interleaved-thinking-2025-05-14` Beta-Header
- Aber **nicht** den `thinking.type="enabled"` + `budget_tokens` Request-Param
- Ohne diesen Param akzeptiert der Provider den Reasoning-Mode nicht → kein Reasoning-Stream

**Hermes sendet:**
```python
kwargs["thinking"] = {"type": "enabled", "budget_tokens": 8000}
kwargs["temperature"] = 1
kwargs["max_tokens"] = max(effective_max_tokens, budget + 4096)
```

**Mein eaccode tut das nicht.** Deshalb `reasoning=0 chars` im Live-Test.

## Soll-Bild

**User-Experience:**
1. `eaccode config set model.reasoning_effort medium` (default) → in REPL erscheint `[Reasoning: ...]` in italic muted vor der normalen Antwort
2. `eaccode config set model.reasoning_effort none` → kein Reasoning, normale Antwort
3. Bei Kreativ-Tasks `eaccode config set model.reasoning_effort xhigh` → langes Reasoning, mehr Tokens für die Antwort

**Architektur:**
```
Agent.run()
  → agent._complete()
    → providers.registry.get(model_id)
    → provider.stream(messages, system=..., max_tokens=..., tools=...)
                                                         ↑
                                    NEU: reasoning_effort aus config
    → StreamChunk(kind="reasoning", content=...)    ← aus thinking_delta
    → StreamChunk(kind="text", content=...)         ← aus text_delta
    → StreamChunk(kind="done")
  → palette._on_token(chunk) → rendert [Reasoning: ...] italic muted
```

## Hermes-Levels (Mapping aus `anthropic_adapter.py` Z. 2240-2243)

```python
THINKING_BUDGET = {"xhigh": 32000, "high": 16000, "medium": 8000, "low": 4000}
ADAPTIVE_EFFORT_MAP = {
    "ultra":   "max",    "max":     "max",
    "xhigh":   "xhigh",  "high":    "high",
    "medium":  "medium", "low":     "low",
    "minimal": "low",
}
```

**Für eaccode (vereinfacht, weil MiniMax-M3 nur `manual` unterstützt, kein `adaptive`):**

```python
REASONING_BUDGET = {
    "minimal": 4000,
    "low":     4000,
    "medium":  8000,
    "high":    16000,
    "xhigh":   32000,
    "max":     32000,
    "ultra":   32000,
}
```

Plus `'none'` = off.

## Inventur (was sich ändert)

| Datei | Aktion | Zeilen |
|---|---|---|
| `src/eaccode/config.py` | `defaults()` um `model.reasoning_effort: "medium"` ergänzen | ~5 |
| `src/eaccode/providers/anthropic.py` | `THINKING_BUDGET` + `REASONING_EFFORT_VALUES` Konstanten, `thinking`-Param in `stream()`, `temperature=1` + `max_tokens += budget` | ~30 |
| `src/eaccode/providers/anthropic.py` | Tests: `thinking`-Param wird durchgereicht, `temperature=1`, `max_tokens` korrekt | ~80 |
| `src/eaccode/agent.py` | `_complete` liest `reasoning_effort` aus config, übergibt an Provider | ~15 |
| `src/eaccode/cli.py` | Optional: `--reasoning-effort LEVEL` Flag fuer `-p` Mode | ~10 |
| `tests/test_agent.py` | Test: Config `reasoning_effort` wird an Provider durchgereicht | ~30 |
| `tests/test_provider_anthropic.py` | Tests: `thinking` auf "enabled", `budget_tokens` korrekt, `temperature=1` | ~60 |
| `tests/test_provider_anthropic.py` | Tests: `reasoning_effort="none"` sendet **kein** `thinking` param | ~20 |
| `docs/manual-test.md` | Reasoning-Block hinzufügen | ~30 |
| `brain/15-features/system/providers.md` | Update: "fix done" | ~5 |

**Gesamt:** ~285 Zeilen, 5-7 Commits.

## Out of Scope (separat)

- **Display-Setting** `display.show_reasoning` (ob Reasoning angezeigt wird) — User-Setting, nicht jetzt
- **Reasoning in Tool-Use-Blöcken** (Hermes-`drop_thinking_only_and_merge_users`) — Phase 2, wenn Tool-Calls stabil
- **Adaptive Thinking** (`thinking.type="adaptive"` + `output_config.effort`) — Hermes-only, MiniMax-M3 unterstützt das laut Code nicht
- **Reasoning-Verifikation via Live-Test** — separater Schritt am Ende

## Schritte (vorgeschlagene Reihenfolge)

### Schritt 1 — Config-Default
`src/eaccode/config.py`: `defaults()` um `model.reasoning_effort: "medium"` ergänzen. Klein, isoliert.

### Schritt 2 — Adapter-Konstanten
`src/eaccode/providers/anthropic.py`: `THINKING_BUDGET` + `REASONING_EFFORT_VALUES` + Helper `_resolve_budget(level)`.

### Schritt 3 — `thinking`-Param einschleusen
`AnthropicProvider.stream()`: lese `reasoning_effort` aus Aufruf-Param, baue `kwargs["thinking"] + kwargs["temperature"] + kwargs["max_tokens"]` gemäß Hermes-Vorbild.

### Schritt 4 — Agent-Config
`agent.py:_complete()`: lies `self.conf.get("model", {}).get("reasoning_effort")` und reiche es an `provider.stream(...)` durch.

### Schritt 5 — Tests
- `test_provider_anthropic.py`: Param wird durchgereicht, `temperature=1`, `max_tokens += budget`
- `test_provider_anthropic.py`: `none` sendet kein `thinking`
- `test_agent.py`: Config-Wert wird an Provider übergeben

### Schritt 6 — Doku
- `docs/manual-test.md`: Reasoning-Block
- `brain/15-features/system/providers.md`: Fix dokumentieren

### Schritt 7 — Live-Test
User-Session: `eaccode config set model.reasoning_effort medium` → `eaccode -p "think step by step. What is 17*23?"` → Erwartung: `[Reasoning: ...]` + `**391**`.

## Was ich von dir brauche (5 Fragen)

1. **Plan freigegeben?**
2. **Default-Level:** `medium` (Hermes-Default) oder nur `low` für eaccode-Phase-1? (Hermes hat `medium` als robusten Default.)
3. **Layer-Status:** Bist du sicher, dass MiniMax-M3 XHigh `thinking.type="enabled"` + `budget_tokens` unterstützt? Hermes-Code geht davon aus, aber wir sollten Live-Test haben BEVOR wir das ausrollen.
4. **CLI-Flag:** Soll `-p` Mode auch `--reasoning-effort LEVEL` bekommen? (Schneller testbar, sonst nur via config.)
5. **Cap auf `max_tokens`:** Hermes addiert `budget_tokens + 4096` zu `max_tokens`. Bei M3 XHigh (1M context, 128k output) reichen 128k + 32k = 160k. Wenn der User `max_tokens=4096` (Default in eaccode) manuell setzt, würden wir 4096+32k=36k forcen. OK so?

## Out-of-Scope (separat, NICHT in diesem Plan)

- Reasoning-Display-Setting (`display.show_reasoning`)
- Reasoning in Tool-Use-Blöcken
- Adaptive Thinking (`thinking.type="adaptive"`)
- Reasoning-Health-Check (loggen ob reasoning leer, inkrementelle bugfixes)

## Risiken

- **MiniMax-M3 unterstützt `thinking` nicht** → leerer Stream, User-Wut. Mitigation: Test mit echter M3-Call vor Code-Merge.
- **`temperature=1` Konflikt** mit anderen Modellen die temperature nicht 1 wollen. Mitigation: nur setzen wenn `thinking` enabled.
- **`max_tokens` override** überschreibt User-Wert. Mitigation: nur wenn `budget_tokens > 0`, dann `max(budget + 4096, user_max_tokens)`.

## Verwandte Pläne

- `2026-08-17_201433-replace-litellm-with-modelsdev.md` — Vorgänger, der litellm raus und Anthropic-Compatible rein
- `brain/15-features/system/providers.md` — Adapter-Architektur
