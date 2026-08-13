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
- ✅ Live-Ping erfolgreich (`minimax/minimax-text-01` → `pong`)

## Offene Punkte
- Weitere MiniMax-Modelle in den Katalog (`KNOWN_MODELS` in router.py)
- MiniMax als Default testen: `/model set-default minimax/minimax-text-01`

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/model-router.md|Model Router]]
