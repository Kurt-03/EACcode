---
name: tool-registry
type: system
status: done
phase: 08-18 plan-g-v5-g1
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# Tool Registry (G.1)

> Hermes-Style Singleton ToolRegistry mit Threading-Lock, generation counter,
> Toolset-Checks, Aliases und Override-Semantik.

## Zweck

eaccode-Tools werden bei Modul-Import via `registry.register(...)` registriert.
Plugin-Tools können Built-ins überschreiben — wenn `override=True` gesetzt ist.
Jeder `register()` / `deregister()` erhöht `_generation`, was Cache-Invalidation
in `tool_search.py` triggert.

## Public Surface (`src/eaccode/registry.py`)

```python
@dataclass
class ToolEntry:
    name: str
    toolset: str
    schema: dict
    handler: Callable
    check_fn: Callable[[], bool] | None = None
    requires_env: list[str] = []
    is_async: bool = False
    description: str = ""
    emoji: str = ""
    max_result_size_chars: int | None = None
    dynamic_schema_overrides: Callable[[], dict] | None = None
    override: bool = False

class ToolRegistry:
    def register(entry) -> None
    def deregister(name) -> None
    def get(name) -> ToolEntry | None
    def list_tools(toolset=None) -> list[ToolEntry]
    def snapshot() -> tuple[list[ToolEntry], dict[str, Callable]]
```

Singleton: `registry.get_instance()` (lazy).

## Sicherheit

- Cross-Toolset-Register ohne `override=True` → Warnung statt harter Fehler
  (Plugin-Surface bleibt aktiv, Built-ins bleiben aktiv)
- `_generation` verhindert stale `tool_search`-Kataloge
- Threading mit `RLock` für Parallel-Subagent-Loops

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.1
- Hermes source: `_ref/hermes/tools/registry.py`

## Tests

`tests/test_registry.py` — Register/deregister, override, generation, thread-safety.
