---
title: models.dev Registry + Local Cache
description: Community-curated model catalog (4000+ models, 109+ providers). Used by eaccode for context windows, max_output, cost, capabilities (reasoning, tool_call, vision, attachment, modalities).
tags: [system, models, catalog, cache, providers]
created: 2026-08-17
updated: 2026-08-17
---

# models.dev Registry + Local Cache

**Modul:** `src/eaccode/models_dev.py`
**Source:** https://models.dev/api.json
**Commit:** `7079bf2`

## Zweck

eaccode nutzt models.dev als **Single Source of Truth** für Modelle:

- **Kontextfenster** (context_window) — z.B. MiniMax-M3 = 1.000.000 Tokens
- **Max Output** — z.B. 128k für MiniMax-M3, 64k für Claude Sonnet 4.5
- **Cost** — input/output/cache_read/cache_write per Million Tokens
- **Capabilities** — reasoning, tool_call, vision, attachment, structured_output
- **Modalities** — input/output (text, image, pdf, audio)
- **Knowledge cutoffs** — release_date, knowledge
- **Status** — alpha, beta, deprecated

Bis 2026-08-17 hatte eaccode eine hardcoded `KNOWN_MODELS` Tabelle mit 4 MiniMax-IDs. Mit models.dev sind es **7 echte Modelle** plus die Capability-Information.

## Cache-Hierarchie (Hermes-Pattern)

```
1. In-memory (TTL 1h)                → sofort, frisch
2. Stale in-memory → background refresh → sofort Stale, Hint am Worker
3. Disk cache (~/.local/eaccode/models_dev_cache.json) → sofort aus Datei
4. network (https://models.dev/api.json) → nur wenn kein Cache
5. failed refresh → 5min process-wide backoff
```

**Wichtig:** Background-Refresh-Thread läuft maximal 1x gleichzeitig (`_models_dev_refresh_in_flight`-Mutex). Bei Fehler wird 5-Minuten-Backoff aktiviert — kein Retry-Storm.

## Public API

```python
from eaccode import models_dev

# Provider-Info
info = models_dev.get_provider_info("minimax")
info.name        # "MiniMax (minimax.io)"
info.env         # ("MINIMAX_API_KEY",)
info.api         # "https://api.minimax.io/anthropic/v1"
info.model_count # 7

# Model-Info
m = models_dev.get_model_info("minimax", "MiniMax-M3")
m.context_window  # 1_000_000
m.max_output      # 128_000
m.reasoning       # True
m.tool_call       # True
m.cost_input      # 0.30
m.cost_output     # 1.20

# Convenience
n = models_dev.get_max_output_tokens("minimax", "MiniMax-M3")  # 128_000

# Listen
models_dev.list_provider_models("minimax")
# ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.5", "MiniMax-M2.1", "MiniMax-M2.0", ...]

# Nur Tool-fähige
models_dev.list_agentic_models("minimax")
```

**Roher Cache:** `models_dev.fetch_models_dev(force_refresh=False, allow_network=True)`

## Cache-Location

- **In-Memory:** Modul-global `dict[str, Any]`
- **Disk:** `~/.local/eaccode/models_dev_cache.json` (oder via `eaccode.config.data_dir()`)

Cache-File ist **Plain JSON** — der gesamte `api.json` Content. Format ist genau wie die models.dev API.

## Init

Beim eaccode-Start wird **einmal** `fetch_models_dev()` aufgerufen (z.B. wenn Agent zum ersten Mal `models_dev.get_model_info(...)` braucht). Das ist **NICHT** im CLI-Init — passiert lazy on first access.

## Tests

`tests/test_models_dev.py` — 27 Tests:
- Parsing-Dataclasses (Context, Cost, Capabilities)
- Query-Helpers (provider, model, list)
- Cache-Hierarchie (in-memory, disk, network)
- Background-Refresh-Verhalten
- Network-Failure-Handling (Backoff)
- Disk-Cache-Save/Load

## Lessons

- **Test-Disk-Isolation wichtig:** Reset-Fixture redirected _get_cache_path to tmp_path, sonst leaken Test-States in den echten User-Cache. (Passierte im ersten Test-Run, siehe Commit-History.)
- **Background-Refresh mocken:** Tests mussten auch `_start_background_refresh_models_dev` patchen, sonst läuft ein echter Thread, der echtes Network triggert.

## Verwandt

- `brain/15-features/system/model-router.md` — der frühere LiteLLM-Router
- `brain/15-features/system/providers.md` — die provider adapters, die models.dev nutzen
- Commit-Log: `7079bf2` (init), `66aeab6` (Anthropic-Adapter)

## Code-Graph (generiert)

- `src/eaccode/models_dev.py` → [[15-features/system/config.md|config.yaml]]

