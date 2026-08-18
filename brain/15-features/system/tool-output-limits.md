---
name: tool-output-limits
type: system
status: done
phase: 08-18 plan-g-v5-g12
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# Tool Output Limits — Configurable Truncation (G.12)

> Power-User tunen Truncation-Thresholds via `config.yaml`, ohne Source-Patch.

## Defaults

```python
DEFAULT_MAX_BYTES = 50_000
DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_LINE_LENGTH = 2000
```

## config.yaml Hook

```yaml
tool_output:
  max_bytes: 100000      # read_file / tool-result cap (chars)
  max_lines: 5000        # read_file pagination + truncation cap
  max_line_length: 2000  # per-line length cap before '... [truncated]'
```

Fehlt der Block → Defaults aktiv (built-in). Kein User-Verhalten ändert sich beim
Upgrade, nur wenn die Section explizit gesetzt wird.

## Cache

`_cached_limits` ist Modul-global, wird beim ersten `get_limits()`-Call
gefüllt. Tests monkey-patchen den Cache.

## API

```python
def get_limits() -> dict[str, int]   # {"max_bytes", "max_lines", "max_line_length"}
def reset_cache() -> None            # für Tests
def _coerce_positive_int(value, default) -> int
```

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.12
- [[15-features/system/config.md|config.yaml]]
- Hermes source: `_ref/hermes/tools/tool_output_limits.py`

## Tests

`tests/test_tool_output_limits.py` — Defaults, custom config, coerce (string→int),
reset_cache idempotent.
