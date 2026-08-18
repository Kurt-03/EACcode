---
number: 0004
title: LiteLLM out, Anthropic SDK direkt
status: accepted
date: 2026-08-17
---

# ADR 0004: LiteLLM raus, Anthropic SDK direkt rein

## Kontext

LiteLLM hat 4 kritische Nachteile in unserem Stack:

1. **Antwort-Verlust bei MiniMax**: LiteLLM routet MiniMax über
   OpenAI-kompatiblen Modus, aber MiniMax-API ist Anthropic-kompatibel
   (`api.minimax.io/anthropic`). LiteLLM bekommt Antwort, aber Teile
   verschwinden in der Konvertierung.
2. **Reasoning nicht trennbar**: MiniMax-M3 sendet Reasoning inline in
   `content` (kein separates `reasoning_content`-Feld). LiteLLM verschluckt
   das.
3. **Stream fragwürdig**: Chunk-Boundary trennt `<TAGS>` von Antwort → leer.
4. **Schwere dependency**: ~30MB zusätzlich, viele transitive Abhängigkeiten.

## Entscheidung

Komplette LiteLLM-Entfernung. Stattdessen:

1. **Direct Anthropic-SDK** (`anthropic>=0.40`)
2. **Eigener Provider-Adapter** (`src/eaccode/providers/anthropic.py`) mit
   MiniMax-spezifischen Anpassungen.
3. **Provider-Registry** (`src/eaccode/providers/registry.py`) für URL-basierte
   Family-Detection.
4. **models.dev Catalog** (`src/eaccode/models_dev.py`) für Model-Catalog.

User hatte in Discord-Style-Hinweis gesagt: "wenn du nicht weiter kommst, schau bei hermes nach".
Hermes' Stream-Implementation (`chat_completion_helpers.py` Z. 3816-3990)
inspirierte den Adapter.

## Konsequenzen

### Pro
- Sauberer Stream, keine Antwort-Verluste bei MiniMax-M3
- Reasoning separat abrufbar (wenn das Model `thinking_delta` sendet)
- MiniMax-Beta-Header können einfach gestrippt werden
- LiteLLM-Update-Risiko entfällt
- Klar definierte Provider-Interfaces

### Contra
- Andere Provider (OpenAI, Grok, Gemini) brauchen eigene Adapter
- Eigener Aufwand für Reasoning-Detection (kommt später)
- Phase 2: Multi-Provider einarbeiten

## Implementierung

| Datei | Zeilen | Zweck |
|---|---|---|
| `src/eaccode/providers/base.py` | 67 | `StreamChunk`, `ToolCall`, `Provider` (abstract base) |
| `src/eaccode/providers/anthropic.py` | 301 | Anthropic-SDK mit Event-Mapping |
| `src/eaccode/providers/registry.py` | 95 | URL-Family-Detection |
| `src/eaccode/providers/__init__.py` | 13 | Public API |
| `src/eaccode/models_dev.py` | 280 | Catalog + Cache (TTL, Disk, Background-Refresh) |
| `src/eaccode/agent.py` | 349 | Refactor: nutzt Provider statt LiteLLM |

**MiniMax-Beta-Header-Stripping**: `interleaved-thinking` wird entfernt,
MiniMax versteht es nicht und terminiert sonst mit `400`.

**auth_token**: Bei non-`sk-ant-`-Keys wird `auth_token` statt `api_key`
gesetzt (MiniMax-Keys fangen mit `sk-cp-` an).

## Tests

- `tests/test_providers_anthropic.py` — 27 Tests (Messages, Stream, ToolCall)
- `tests/test_providers_registry.py` — 16 Tests (URL-Family, Per-Call-Cache)
- `tests/test_models_dev.py` — 27 Tests (Cache-Hierarchy, TTL, Retry)
- `tests/test_agent.py` — komplett neu mit `FakeProvider` (25 Tests)

## Resultat (Live-verifiziert 08-18)

```
$ eaccode -p "Hi! Was kannst du?"
[Smart-Mode system-prompt mit Mode-Hint]
+ kompletter Output Body
+ Status-Line MiniMax-M3

$ eaccode permissions mode smart
+ Auto-Approve safe commands
+ Aux-LLM für dangerous
```

## Status

Accepted — komplett am 08-17 umgesetzt, +streaming-bug-Fix 08-18.

## Verwandt

- [[15-features/system/providers.md|Provider Architecture]]
- [[15-features/system/models-dev.md|models.dev Catalog]]
- [[15-features/providers/minimax.md|minimax Provider]]
