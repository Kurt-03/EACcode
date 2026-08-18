---
name: tool-search
type: system
status: done
phase: 08-18 plan-g-v5-g2
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# Tool Search Subsystem (G.2)

> BM25-basiertes Deferred-Tool-Discovery. Core-Tools bleiben sichtbar, der
> Rest wandert hinter `tool_search` / `tool_describe` / `tool_call`-Bridge.

## Zweck

Bei wachsender Tool-Liste (>50 Tools) frisst das Tool-Manifest den Context.
Hermes' Lösung: Token-Budget für den Tool-Katalog, Rest "deferred". Das Modell
`tool_search(query="git")` → kriegt Mini-Beschreibungen der Treffer → `tool_describe(name="git_commit")` → kriegt volle Schema → `tool_call(name="git_commit", args=...)` → executes.

## Config

```python
@dataclass
class ToolSearchConfig:
    enabled: str = "auto"        # off / on / auto
    min_tokens: int = 0
    catalog_budget_pct: float = 0.10   # 10% of context window
```

`auto` = aktivieren sobald Catalog-Size > `min_tokens` + `budget_pct * context_window`.

## Core-Tools

Diese sind *immer* sichtbar — unabhängig vom Budget:

```python
{"read_file", "write_file", "patch_file", "patch_multiple",
 "file_edit", "undo_edit", ...}
```

## Bridge-Tools

```python
tool_search(query)         → list[tool-summary]
tool_describe(name)        → full schema
tool_call(name, **args)    → executes the deferred tool
```

## Integration

- `registry.ToolRegistry.snapshot()` ist die Source-of-Truth
- `tool_search` invalidiert sich bei `_generation`-Change

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.2
- Hermes source: `_ref/hermes/tools/tool_search.py`

## Tests

`tests/test_tool_search.py` — Core-Set, Budget-Triggern, BM25-Relevanz, Bridge-Resolve.
