---
name: path-security
type: system
status: done
phase: 08-18 plan-h-v4-stufe-2
date: 2026-08-18
tags: [type/feature, feature/system, hermes, security, validation]
---

# Path Security (Hermes-Style)

> Strengere Validierung für Pfade (Plan H.minimal v4, Tag 4).

## Helpers

| Helper | Was |
|---|---|
| `has_traversal_component(path)` | ".." detection (auch in mixed paths) |
| `is_blocked_device(path)` | NUL, CON, COM1, /dev/null |
| `is_unc_path(path)` | `\\server\share` detection |
| `is_path_within_dir(path, root)` | Strict containment |
| `validate_within_dir(path, root)` | All-in-one validator (raises WorkspaceError) |

## Blocked Devices (Windows)

CON, PRN, AUX, NUL, COM1-COM9, LPT1-LPT9

## Blocked Devices (POSIX)

`/dev/null`, `/dev/zero`, `/dev/random`, `/dev/urandom`, `/dev/stdin/stdout/stderr`, `/dev/tty`, `/dev/console`, `/dev/ptmx`, `/dev/full`, `/dev/loop0`

## Reference

- Code: `src/eaccode/path_security.py`
- Tests: `tests/test_path_security.py`