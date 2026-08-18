---
name: blocked-list
type: system
status: done
phase: 08-18 plan-c-c8
date: 2026-08-18
tags: [type/feature, feature/system, permissions, hermes]
---

# Persistent Blocked-Pattern List (Plan C, C.8)

> Wenn User „deny_always" wählt, wird das Pattern hier persistiert. Überlebt
> eaccode-Neustarts. Match gegen `tool_name + json args`-Call-Text.

## Storage

```
~/.local/share/eaccode/blocked.json
```

Schemaversioniert (`_FILE_VERSION = 1`). Threadsafe via `_LOCK`.

## BlockedPattern-Schema

```python
{
    "id": uuid-hex,
    "pattern": "<tool-call-text>",
    "reason": "user reason or auto-generated",
    "created_at": "<iso8601>",
    "scope": "always"   # only one scope for now
}
```

## API

```python
class BlockedPatternsStore:
    def add(pattern, reason="") -> BlockedPattern
    def remove(pattern_id) -> bool
    def find(call_text: str) -> BlockedPattern | None
    def list_all() -> list[BlockedPattern]
    def clear() -> int   # returns count
```

## Wire-Position

`permissions.py:check()` Layer 3 (nach deny-rules, vor sensitive-paths):

```python
blocked = blocked_store.find(call_text)
if blocked:
    return Decision(scope="deny_always", reason=f"blocked:{blocked.id}")
```

Plus `/approvals denied-list list/remove` als CLI.

## Verknüpft

- [[15-features/system/permissions.md|permissions]]
- Hermes source: Pattern aus `_ref/hermes/approval.py:blocked-list`

## Tests

`tests/test_blocked.py` — Add, Find by exact/regex, Remove, Persistence over
restart, Schema-Migration v0→v1.
