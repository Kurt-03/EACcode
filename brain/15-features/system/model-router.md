# Model Router

**Status:** DEPRECATED as of 2026-08-17. Kept as back-compat shim. Use `eaccode.providers` instead.

Warum? LiteLLM normalisiert MiniMax-Streams zu OpenAI-Format und verliert dabei `reasoning_content`-Reihenfolge. Plus falsche Auth-Header und Beta-Headers. Siehe `brain/15-features/system/providers.md` für die neue Architektur.

Commit-Log: `cd25ce3` (deprecation shim), `9d45ce9` (agent refactor).

---

---
name: model-router
type: system
status: done
phase: A3
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Model Router (BYOK)

## Zweck
Alle Modelle über eine Schnittstelle (LiteLLM): `provider/model`-IDs,
Fallback-Chain, Live-Ping, Modell-Katalog.

## Implementierung
- `src/eaccode/router.py` — `resolve_api_key`, `model_chain`, `all_model_ids`,
  `completion_response` (roh) / `completion_text` (Text), `call_model`
  (Fallback), `ping_model`
- `extra_kwargs` für Tool-Calling + `max_tokens`
- `KNOWN_MODELS`-Katalog pro Provider (UX-Hilfe, nicht exhaustiv)

## Kommandos
```
/provider add|list|remove|set-key
/model list|add|set-default|set-fallback|ping
```

## Tests
`tests/test_router.py` + `tests/test_commands.py` (TestProvider/TestModel)

## Offene Punkte
- Kosten-/Latenz-Metadaten im Katalog (D5-Vorbereitung)
- Routing nach Task-Typ (D5): starkes Modell für Code, günstiges für Routine

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[ADR/0002-phase-a-architecture.md|0002-phase-a-architecture]]

## MiniMax-M3 Provider-Setup (08-17, Nutzerwunsch)

Hermes-MiniMax-Spezialbehandlung übernommen — ohne sie sind Antworten
abgeschnitten oder leer.

### Anthropic-kompatibler Endpunkt

MiniMax-M3 muss über den Anthropic-Adapter angesprochen werden, sonst
liefert NVIDIA NIM einen HTTP 200 mit leerem `choices[]`-Payload zurück.
**Pflicht:** `base_url: https://api.minimax.io/anthropic` in
`providers.minimax`.

### max_tokens zwingend

NVIDIA NIM → 200/leer wenn `max_tokens` fehlt. eaccode setzt einen
Default von 4096 wenn der Caller keinen eigenen Wert übergibt.
`router._completion_kwargs` prüft `provider_name == "minimax"` und
setzt den Default **nur** wenn nicht schon ein `max_tokens` im
`extra_kwargs` ist.

### Reasoning sichtbar (Anthropic-Format)

MiniMax-M3 sendet Reasoning als **separates `delta.reasoning_content`-Feld**
(wenn über Anthropic-Adapter). eaccode:
- Liest `delta.reasoning_content` in `agent._complete` (Stream-Loop)
- Reicht es durch `on_token(text, kind="reasoning")` an die UI
- `palette.ChatApp._on_token` formatiert Reasoning als `[Reasoning: ...]`
  in italic muted (`chat.reasoning` = `italic #8b8b8b`)
- Sobald die Antwort kommt (`kind="answer"`), wird die Bracket
  geschlossen und der Antwort-Stream beginnt auf einer neuen Zeile

### Tests

- `tests/test_router.py::TestMinimaxSetup` — 5 Tests für
  `max_tokens`-Default, `base_url`-Propagation, `KNOWN_MODELS`
- `tests/test_agent.py::TestStreamingReasoningContent` — 2 Tests
  für `reasoning_content`-Field-Routing

### User-Config-Beispiel

```yaml
providers:
  minimax:
    api_key: sk-cp-...
    base_url: https://api.minimax.io/anthropic
    models:
      - minimax/MiniMax-M3
      - minimax/MiniMax-M2.5
      - minimax/MiniMax-M2.1
      - minimax/MiniMax-M2.1-lightning
```

### Hermes-Referenz

- `C:/Projekte/_ref/hermes/agent/auxiliary_client.py:8010` —
  `_ANTHROPIC_COMPAT_PROVIDERS = frozenset({"minimax", "minimax-oauth", "minimax-cn"})`
- `agent_runtime_helpers.py:1760-1779` — `reasoning_content`-Field-Handling
- `agent_runtime_helpers.py:665-670` — Carry reasoning_content across turns
- `auxiliary_client.py:8190` — `minimaxai/minimax-m3` NVIDIA NIM Caveat

## Code-Graph (generiert)

- `src/eaccode/router.py` → —

