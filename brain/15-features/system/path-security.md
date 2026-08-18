---
name: path-security
type: system
status: done
phase: 08-18 plan-h-stufe-2
date: 2026-08-18
tags: [type/feature, feature/system, security, hermes]
---

# Path-Security (Plan H.minimal v4, Stufe 2)

> Hermes-Style Helpers beyond the basic `workspace.rewrite_path` check. Strict
> containment, traversal/device/UNC detection.

## Zweck

`workspace.py` blockiert Pfade *außerhalb* des Workspace. Das reicht für 95 %
der Fälle. Für die `/approvals allow-path <external>`-Bridge brauchen wir
**explizite** Validation, dass ein freigegebener Pfad auch wirklich unter
seinem Root liegt — inklusive Symlink-Resolve, Traversal-Component,
Device-Path- und UNC-Detection.

## API

| Funktion | Was sie tut |
|---|---|
| `has_traversal_component(path)` | `".."` als Segment ODER `"/./../etc/passwd"`-Tricks |
| `is_blocked_device(path)` | Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) **und** POSIX-Devices (`/dev/null`, `/dev/zero`, …) |
| `is_unc_path(path)` | `\\server\share` ODER `//server/share` (Cross-Platform) |
| `is_path_within_dir(path, root)` | Strict containment via `Path.resolve(strict=False)` + `relative_to` |
| `validate_within_dir(path, root)` | Raises `WorkspaceError` mit Code `path_traversal` / `symlink_escape` / `blocked_device` / `unc_path` / `path_outside_root` |

## WorkspaceError-Codes

| Code | Trigger |
|---|---|
| `path_traversal` | `..` als Segment |
| `unc_path` | UNC-Share-Form |
| `blocked_device` | Windows-Device-Name ODER POSIX-Device-Pfad |
| `symlink_escape` | Symlink resolved außerhalb Root |
| `path_unresolvable` | `Path.resolve` raises `OSError` |
| `path_outside_root` | Sonstige Outsider |

## Integration

`/approvals allow-path` validiert jeden freigegebenen Pfad via
`validate_within_dir(path, Path.cwd())`. Wenn der Pfad außerhalb CWD liegt,
muss er explizit `--once` oder `--session` getaggt sein (sonst ASK).

## Tests

`tests/test_path_security.py` — Traversal, Device, UNC, Symlink-Resolve,
Containment am Root-Boundary, doppelte Validation (Original + resolved).

## Verknüpft
[[15-features/system/workspace.md|workspace]] · [[15-features/system/permissions.md|permissions]]

Plan: `.hermes/plans/2026-08-18_213000-stufe-2-permission-bridge.md`
Hermes source: `_ref/hermes/tools/path_security.py` (Hermes-Verbatim analog)

## Code-Graph (generiert)

- `src/eaccode/path_security.py` → [[15-features/system/workspace.md|workspace]]

