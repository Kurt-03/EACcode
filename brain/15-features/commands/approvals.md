---
name: approvals
type: command
status: done
phase: 08-18 plan-h-v4-stufe-2
date: 2026-08-18
tags: [type/feature, feature/command, workspace, hermes]
---

# /approvals

> Manage workspace allow/deny rules (Plan H.minimal v4, Stufe 2).

## Commands

```
/approvals allow-path <path> [--once|--session|--always]
/approvals deny-path <path> [--once|--session|--always]
/approvals list
/approvals reset
```

## Scopes

| Scope | Behavior |
|---|---|
| `once` | One-shot, used once and discarded |
| `session` | Lifetime of current session, lost on exit |
| `always` | Persisted in `~/.local/share/eaccode/approvals.json` |

## Glob-Pattern

`allow-paths` und `deny-paths` können Glob-Patterns enthalten (`?`, `*`, `[seq]`).

## Beispiel

```
❯ /approvals allow-path C:/Users/admin/Desktop --session
✓ Allowed C:/Users/admin/Desktop (scope: session)

❯ /approvals list
Allow-paths:
  - C:/Users/admin/Desktop  (session)
```

## Reference

- Code: `src/eaccode/commands.py::run_approvals_command`
- Persistence: `src/eaccode/approvals_store.py`
- Tests: `tests/test_approvals.py`