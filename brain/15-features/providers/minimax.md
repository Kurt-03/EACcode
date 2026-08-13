---
name: minimax
type: provider
status: done
phase: A3
date: 2026-08-13
tags: [type/feature, feature/provider]
---

# Provider: MiniMax

## Zweck
MiniMax-Modelle via LiteLLM — **erster Provider mit live verifiziertem Call**
(2026-08-13: `model ping` → `pong`).

## Konfiguration (in config.yaml)
```yaml
providers:
  minimax:
    api_key: <sk-…>   # via verdecktem Prompt gesetzt; Status: key: set (file)
```

## Bedienung
```
/provider add minimax
/provider set-key minimax      ← verdeckte Eingabe
/model ping minimax/minimax-text-01
```

## Status
- ✅ Key gesetzt (Stand 2026-08-13)
- ✅ Live-Pings erfolgreich: `minimax/MiniMax-M3` → `pong`, `minimax/minimax-text-01` → `pong`

## Modelle (Katalog)
- `minimax/MiniMax-M3` (2026-08-13 live getestet)
- `minimax/minimax-text-01` (2026-08-13 live getestet)

## Offene Punkte
- MiniMax als Default testen: `/model set-default minimax/MiniMax-M3`

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/model-router.md|Model Router]]
