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
[[15-features/README.md|Feature-Register]] · [[adr/0002-phase-a-architecture.md|ADR 0002]]

## Code-Graph (generiert)

- `src/eaccode/router.py` → [[15-features/system/config.md|Config]]

