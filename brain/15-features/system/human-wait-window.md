---
name: human-wait-window
type: system
status: done
phase: 08-18 plan-c
date: 2026-08-18
tags: [type/feature, feature/system, hermes]
---

# Human Wait Window — Pause Batch-Deadlines während User-Input

> ContextVar zählt, ob gerade ein User-Prompt offen ist. Cron, Batch-Worker
> etc. pausieren ihren Deadline-Countdown während Ask-Operationen.

## API

```python
@contextlib.contextmanager
def human_wait_window() -> Iterator[None]
    # counter-style: nested windows addieren depth

def is_human_wait_active() -> bool
    # True wenn depth > 0
```

ContextVar: `_human_wait_depth: ContextVar[int] = ContextVar("eaccode_human_wait_depth", default=0)`

## Verwendung

```python
from eaccode.human_wait_window import human_wait_window, is_human_wait_active

if is_human_wait_active():
    # Wait for the user prompt to finish before pushing the next batch item
    ...
```

## Wire-Position

Im REPL `_ask()`/`_ask_with_choices()` — wraps jeden Inline-Prompt.
Im Cron-Worker: Batch-Items werden zurückgestellt, solange `is_human_wait_active()`.

## Verknüpft

- [[15-features/system/permissions.md|permissions]]
- Hermes pattern: human_wait + scheduler pause

## Tests

`tests/test_human_wait_window.py` — Enter/Exit, Nested, Concurrency (Task-local),
Cleanup on exception (Counter wieder bei 0).
