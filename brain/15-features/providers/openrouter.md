---
name: openrouter
type: provider
status: done
phase: A3
date: 2026-08-13
tags: [type/feature, feature/provider]
---

# Provider: OpenRouter

## Zweck
Zugriff auf viele Modelle über eine API (Claude, Llama, DeepSeek, …) — aktuell
das Default-Modell: `openrouter/anthropic/claude-sonnet-4`.

## Konfiguration (in config.yaml)
```yaml
providers:
  openrouter:
    api_key_env: OPENROUTER_API_KEY   # oder api_key via /provider set-key
```

## Bedienung
```
/provider add openrouter --api-key-env OPENROUTER_API_KEY
/provider set-key openrouter        ← verdeckte Eingabe
/model ping openrouter/anthropic/claude-sonnet-4
```

## Status
- Key aktuell **nicht gesetzt** (Stand 2026-08-13) — echte Calls warten auf Key

## Offene Punkte
- O2 (Provider-Erstauslieferung): OpenRouter-first bestätigen?

## Verknüpft
[[../README|Feature-Register]] · [[model-router|Model Router]]
