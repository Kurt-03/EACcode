---
name: ollama
type: provider
status: done
phase: A3
date: 2026-08-13
tags: [type/feature, feature/provider]
---

# Provider: Ollama (lokal)

## Zweck
Lokale Modelle ohne API-Key — der BYOK-Fallback (aktuell `ollama/llama3.2`).

## Konfiguration
```yaml
providers:
  ollama:
    base_url: http://localhost:11434
```

## Bedienung
```
/provider add ollama --base-url http://localhost:11434
/model add ollama/deepseek-r1 --base-url http://localhost:11434   # custom
/model ping ollama/llama3.2
```

## Status
- Konfiguriert (Stand 2026-08-13); Live-Ping hängt davon ab, ob Ollama läuft

## Offene Punkte
- (keine)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/model-router.md|Model Router]]
