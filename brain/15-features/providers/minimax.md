---
name: minimax
type: provider
status: done
phase: A3 + 08-17 (litellm-out, Anthropic-SDK) + 08-18 (smart-mode)
date: 2026-08-13 / updated 2026-08-18
tags: [type/feature, feature/provider, anthropic-compatible]
---

# Provider: MiniMax

## Zweck
MiniMax-Modelle via **Anthropic-SDK** (Anthropic-Compatible Endpunkt auf
`api.minimax.io/anthropic`). Bis 08-17 via LiteLLM; 08-17 komplett auf direkten
Anthropic-SDK umgestellt — bessere Stream-Stabilität, kein Antwort-Verlust.

## Konfiguration
```yaml
providers:
  minimax:
    api_key: sk-cp-...    # via verdecktem Prompt gesetzt
    api_key_env: MINIMAX_KEY
    base_url: https://api.minimax.io/anthropic
```

## Live-verifiziert
- ✅ `MiniMax-M3` → 8+ Test-Pings (08-13, 08-17, 08-18)
- ✅ Streaming-Antworten komplett (nach Bug-Fix 08-18)
- ✅ Smart-Mode Aux-LLM Reviews funktionieren mit `MiniMax-M3` als Model

## Modelle (08-18 live getestet)
- `minimax/MiniMax-M3` (Haupt-Model, alle Funktionen)
- `minimax/minimax-text-01` (älter)
- `minimax/MiniMax-M2.7` (älter)

## ⚠ Wichtig: Reasoning
`MiniMax-M3` sendet **`reasoning_content` nicht** über den Anthropic-COMPAT
Endpunkt — Reasoning wird inline in `content` als normaler Text gegeben.
Nicht über `thinking_delta`-Event trennbar.

→ `display.show_reasoning` Toggle (Hermes-Desktop) hat keine Wirkung.
→ Eaccode-Plan: `model.reasoning_effort` + `thinking.type="enabled"` — siehe
`.hermes/plans/2026-08-17_192147-reasoning-effort-thinking.md` (Phase 2).

## Bedienung
```
/provider add minimax
/provider set-key minimax      ← verdeckte Eingabe
/model set-default minimax/MiniMax-M3
/model ping minimax/MiniMax-M3
```

## Anthropic-Beta-Header-Stripping

Im Provider-Code (`src/eaccode/providers/anthropic.py`) wird der Header
`interleaved-thinking` entfernt, weil MiniMax ihn nicht versteht und den
Anschluss sonst mit `400 Bad Request` terminiert.

## Verknüpft
[[15-features/README.md|Feature-Register]] ·
[[15-features/system/providers.md|Provider Architecture]] ·
[[15-features/system/models-dev.md|models.dev Catalog]] ·
[[15-features/system/smart-approval.md|Aux LLM Reviewer]]