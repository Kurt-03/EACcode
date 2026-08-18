---
name: providers-registry
type: system
status: done
phase: 08-17 anthropic-sdk
date: 2026-08-17
tags: [type/feature, feature/system]
---

# Provider Registry (Detektion + Cache)

> Mappt `provider_name + config → Provider-Instanz`, mit `base_url`-Detection
> für Anthropic-Family.

## Familien-Detektion

```python
_FAMILY_ANTHROPIC = "anthropic"
_FAMILY_UNSUPPORTED = "unsupported"

# Anthropic-Family: base_url endet mit /anthropic ODER Name in
#   {anthropic, minimax, minimax-oauth, minimax-cn}
# Sonst: unsupported.
```

`detect_family(provider_name, provider_config)` ist die zentrale Detection.

## Cache

```python
# (provider_name, base_url, api_key) -> Provider
_provider_cache: dict = {}
```

Drei Inputs ergeben eine eindeutige Provider-Instanz — Cache-Hit überspringt
die Construction. Tests rufen `reset_cache()` zum Aufräumen.

## API

```python
def get(provider_name, provider_config, *, model="", timeout=60.0) -> Provider
def reset_cache() -> None
def _api_key_from_config(provider_config) -> str   # env wins over file
```

`api_key_env` (env-var-name) → bevorzugt; `api_key` (literal in config.yaml)
nur als Fallback. So können User den Key in `.env` halten.

## Out-of-Scope

OpenAI-Chat-Completions-Adapter. Erkennt man an `family == "unsupported"`
und schmeißt `NotImplementedError`.

## Verknüpft

- [[15-features/providers/anthropic.md|anthropic]]
- [[15-features/providers/base.md|base]]
- [[15-features/system/providers.md|providers]]
- [[15-features/system/model-router.md|Model Router]]
