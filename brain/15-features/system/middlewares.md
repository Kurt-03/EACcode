---
name: middlewares
type: system
status: done
phase: 08-18 plan-g-v5-g10
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# Tool-Call Middlewares (G.10)

> Hermes-Pattern: pre_request rewritet Args (oder vetos), pre_execution
> short-circuited mit Return-Wert.

## Phasen

| Phase | Input | Return | Effekt |
|---|---|---|---|
| **PRE_REQUEST** | `(name, args)` | `dict` (replaced) / `None` (pass-through) | Args werden vor dem Provider-Call umgeschrieben |
| **PRE_EXECUTION** | `(name, args)` | `str` (short-circuit) / `None` | Tool wird gar nicht aufgerufen, stattdessen String-Result |

## Public API

```python
PRE_REQUEST = "pre_request"
PRE_EXECUTION = "pre_execution"

Middleware = Callable[[str, dict], dict | str | None]

def register_pre_request(fn) -> None
def register_pre_execution(fn) -> None
def run_pre_request(name, args) -> dict
def run_pre_execution(name, args) -> str | None
```

## Beispiel

```python
def strip_relative_paths(name, args):
    if name in {"write_file", "patch_file"}:
        if "path" in args and not args["path"].startswith("/"):
            args = {**args, "path": "/workspace/" + args["path"]}
    return args

register_pre_request(strip_relative_paths)
```

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.10
- Hermes source: `_ref/hermes/tools/model_tools.py:_tool_*_middleware`

## Tests

`tests/test_middlewares.py` — Pre-Request rewrite, Pre-Execution short-circuit,
chained middlewares (last-registered wins), None-pass-through.
