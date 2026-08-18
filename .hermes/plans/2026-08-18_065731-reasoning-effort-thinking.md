# Reasoning-Effort + Thinking-Param aktivieren — Plan

> **Status:** `DRAFT` — wartet auf User-Freigabe. Nicht ausführen.
> **Auslöser:** Hermes Desktop hat ein Model-Settings-Panel mit **Thinking** Toggle + **Effort** (siehe Screenshot 08-18). Mein eaccode sendet aktuell **keinen** `thinking.type="enabled"` + `budget_tokens` Param, darum kein `thinking_delta`-Stream.
> **Quelle:** `C:/Projekte/_ref/hermes/agent/anthropic_adapter.py` Z. 2262-2278 (THINKING_BUDGET + Mapping).

## Diagnose (warum jetzt sichtbar)

**MiniMax-M3 XHigh sendet Reasoning-Delta NICHT** (live verifiziert am 08-18 mit echtem API-Call): 0 `thinking_delta` Events trotz korrektem `thinking.type="enabled"` + `budget_tokens` Param. Antwort: 2 chars im Text-Stream, Reasoning: 0 chars.

**Zwei Bugs sind überlagert:**
1. Mein `AnthropicProvider` sendet den `thinking`-Param **nicht** (nur den `interleaved-thinking-2025-05-14` Beta-Header)
2. Selbst wenn ich's sende, ignoriert MiniMax-M3 XHigh ihn (oder antwortet mit Reasoning inline im text_delta, was wir nicht als `thinking_delta` zurückbekommen)

**Hermes sendet es (anthropic_adapter.py Z. 2262-2278):**
```python
kwargs["thinking"] = {"type": "enabled", "budget_tokens": 8000}
kwargs["temperature"] = 1
kwargs["max_tokens"] = max(effective_max_tokens, budget + 4096)
```

**Mein eaccode tut das nicht.** Deshalb `reasoning=0 chars` im Live-Test.

**Konsequenz:**
- Plan baut Reasoning-Param trotzdem ein (für native Claude, Kimi, DeepSeek)
- `reasoning_kwargs()` als Provider-Method: jeder Adapter mappt individuell
- MiniMax-M3 wird auch nach dem Fix KEIN Reasoning-Stream liefern, aber Code ist ready für andere Provider/Modelle

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
| `src/eaccode/providers/base.py` | `Provider` Protocol: `reasoning_kwargs(effort: str) -> dict | None` Methode | ~10 |
| `src/eaccode/providers/anthropic.py` | `THINKING_BUDGET` + `REASONING_EFFORT_VALUES`, `thinking`-Param + `temperature=1` + `max_tokens` Adjustment; `reasoning_kwargs()`-Methode | ~40 |
| `src/eaccode/agent.py` | `_complete` liest `reasoning_effort` aus config, ruft `provider.reasoning_kwargs()`, mergt in kwargs; `max_tokens` automatisch angehoben | ~25 |
| `src/eaccode/cli.py` | Optional: `--reasoning-effort LEVEL` Flag fuer `-p` Mode | ~10 |
| `tests/test_provider_anthropic.py` | `reasoning_kwargs()` Tests: medium/xhigh/none; `thinking.type="enabled"` + `budget_tokens`; `temperature=1`; `max_tokens`-override | ~80 |
| `tests/test_agent.py` | Test: `reasoning_effort` aus Config wird an Provider durchgereicht; bei `none` kein Override | ~40 |
| `docs/manual-test.md` | Reasoning-Block | ~30 |
| `brain/15-features/system/providers.md` | Update: "fix done + was geht bei welchem Provider" | ~10 |

**Gesamt:** ~250 Zeilen, 5-7 Commits. **Provider-agnostic design**: jeder Adapter implementiert `reasoning_kwargs()` individuell. Anthropic-Familie nutzt `thinking.type` + `budget_tokens`. OpenAI-Compatible (später) nutzt `reasoning_effort` direkt. Für Provider ohne Reasoning support retourniert `reasoning_kwargs()` `None`.

## Out of Scope (separat)

- **Display-Setting** `display.show_reasoning` (ob Reasoning angezeigt wird) — User-Setting, nicht jetzt
- **Reasoning in Tool-Use-Blöcken** (Hermes-`drop_thinking_only_and_merge_users`) — Phase 2, wenn Tool-Calls stabil
- **Adaptive Thinking** (`thinking.type="adaptive"` + `output_config.effort`) — Hermes-only, MiniMax-M3 nicht, eaccode Phase 1 nutzt `manual`-Mode
- **OpenAI-Reasoning** (o1, o3, gpt-5): kommt mit OpenAI-Provider-Adapter (Phase 2). `reasoning_kwargs()` für OpenAI-Familie wird `{"reasoning_effort": "..."}` mappen.
- **Grok-Reasoning**: kommt mit xAI-Provider (Phase 2). Same Pattern.
- **Google Gemini-Reasoning**: kommt mit Vertex/Gemini-Adapter (Phase 2). Andere Param-Name (`thinkingBudget`).
- **Claude-4.6+ Adaptive Thinking**: Hermes-Spezialität, nicht für eaccode-Phase-1
- **Reasoning-Health-Check** (loggen ob reasoning leer, inkrementelle bugfixes)

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
2. **Default-Level:** `medium` (Hermes-Default) oder `low` (eaccode-Phase-1 defensiv)?
3. **Layer-Status:** Live verifiziert: MiniMax-M3 XHigh unterstützt `thinking_delta`-Stream NICHT (auch mit korrektem Param 0 Events). **Trotzdem** Param senden, weil:
   - Andere Anthropic-Compatible-Provider (Kimi, DeepSeek) funktionieren damit
   - Native Claude-Modelle funktionieren
   - Bei zukünftigen M3-Versionen (oder anderen Provider) ist Code ready
4. **CLI-Flag:** Soll `-p` den `--reasoning-effort LEVEL` bekommen? Vorteil: schneller testbar, gilt für alle Provider
5. **Cap auf `max_tokens`:** `max_tokens = max(user_max, budget + 4096)` (Hermes-Stil). Wenn User z.B. `max_tokens=4096` manuell setzt + `xhigh` (32k budget), forcen wir 36k. OK so?

**Bonus-Frage:** Bei `reasoning_effort="none"` soll der Param komplett **weg** sein (kein `thinking: {type: "disabled"}`). Bestätigt — Hermes-muster. OK?

## Out-of-Scope (separat, NICHT in diesem Plan)

- Reasoning-Display-Setting (`display.show_reasoning`)
- Reasoning in Tool-Use-Blöcken
- Adaptive Thinking (`thinking.type="adaptive"`)
- Reasoning-Health-Check (loggen ob reasoning leer, inkrementelle bugfixes)

## Risiken

- **MiniMax-M3 XHigh ignoriert `thinking`-Param** (live verifiziert: 0 `thinking_delta` Events). Mitigation: Reasoning bleibt leer für MiniMax-M3 — wird im UI so behandelt (Reasoning-Block ausgeblendet wenn 0 chars). Andere Provider funktionieren.
- **`temperature=1` Konflikt** mit Modellen die temperature nicht 1 wollen. Mitigation: nur setzen wenn `reasoning_effort != "none"`.
- **`max_tokens` override** überschreibt User-Wert. Mitigation: nur wenn `budget_tokens > 0`, dann `max(budget + 4096, user_max_tokens)`.
- **Reasoning-ReasoningEffort !== Anthropic-Param** bei OpenAI-Compatible. Mitigation: `reasoning_kwargs()` als Provider-Method — jeder Adapter mappt individuell.
- **Reasoning-Inhalte Leaking** über Modell-Wechsel. Mitigation: Reasoning-Content ist transport-by-Adapter, nicht im `messages`-History gespeichert (kein Leakage).

## Verwandte Pläne

- `2026-08-17_201433-replace-litellm-with-modelsdev.md` — Vorgänger, der litellm raus und Anthropic-Compatible rein
- `brain/15-features/system/providers.md` — Adapter-Architektur
