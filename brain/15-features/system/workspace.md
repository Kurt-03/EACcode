---
name: workspace
type: system
status: done
phase: 08-18 plan-h-v3-stufe-1
date: 2026-08-18
tags: [type/feature, feature/system, security, hermes]
---

# Workspace (Plan H.minimal v3, Stufe 1)

> Workspace-Isolation für **eaccode-Tools** (write_file, file_edit, etc.).
> `run_command` komplett entfernt (08-18).

## Was Workspace macht

- Default workspace = `<cwd>/.eaccode-workspace/`
- Pfad-Tools (read_file, write_file, list_files, search_files, file_edit, patch_file) gehen durch `rewrite_path()`
- `..` → blockiert (path-traversal)
- Absolute Pfade außerhalb workspace → blockiert
- Symlinks → resolved + geprüft

## Sandbox-Targets

| Tool | Sandbox |
|---|---|
| read_file, write_file | ✓ |
| list_files, search_files | ✓ |
| file_edit, patch_file, patch_multiple, undo_edit | ✓ |
| git_*, repo_* | cwd=workspace (partial) |
| memory_* | exempt (cross-session) |
| create_skill, improve_skill | exempt (cross-session) |
| browser_* | hat eigene Sandbox |
| http_get, web_search | URLs |
| ~~run_command~~ | **entfernt** |

## Exempt Paths

Diese bypassen Workspace-Isolation:
- `MEMORY.md`, `USER.md`
- `/skills/` (Skills persistent im echten Profile)
- `.telegram-bot-config`

## Live-Test

```
$ cd /path/to/myproject
$ eaccode

> lies Desktop-Datei test.py
→ ERROR: cannot access (outside workspace)

> schreibe test.py
→ Schreibt nach .eaccode-workspace/test.py ✓

> cat ../secrets.txt
→ ERROR: path-traversal blocked

> git status
→ git status im workspace

> /approvals allow-path C:/Users/admin/Desktop  # Stufe 2+
→ ab jetzt erlaubt
```

## Endstand (Stufe 1, committed `bcf8b75`)

- 896 Tests grün
- ~1050 LOC neu (workspace + sandboxing)
- 23 workspace-tests + bestehende Tests angepasst

---

# Stufe 2: Permission-Bridge (Plan H.minimal v4)

> User kann Pfade explizit aus der Sandbox raus-mappen.

## Was Stufe 2 macht

- `/approvals allow-path <path> [--once|--session|--always]`
- `/approvals deny-path <path> [--once|--session|--always]`
- `/approvals list` - zeigt alle Regeln
- `/approvals reset` - löscht session/once-scoped
- `~/.local/share/eaccode/approvals.json` - persistent storage
- Hermes-Style strict validation: blocked_devices, UNC, traversal

## Slash-Commands

```
❯ /approvals allow-path C:/Users/admin/Desktop --session
✓ Allowed C:/Users/admin/Desktop (scope: session)

❯ /approvals deny-path C:/Users/admin/secrets --always
✓ Denied C:/Users/admin/secrets (scope: always)

❯ /approvals list
Allow-paths:
  - C:/Users/admin/Desktop  (session)
Deny-paths:
  - C:/Users/admin/secrets  (always)
```

## Hermes-Style Helpers

- `validate_within_dir(path, root)` - strict containment
- `has_traversal_component(path)` - ".." detection
- `is_blocked_device(path)` - NUL, CON, COM1, /dev/null, etc.
- `is_unc_path(path)` - `\\server\share` detection

## Endstand (Stufe 2)

- 945 Tests grün
- 5 neue Module: `workspace.py` (extended), `approvals_store.py`, `path_security.py`, + 35 new tests
- ~600 LOC neu (Stufe 2)

## Reference

- Stufe 1 Plan: `.hermes/plans/2026-08-18_210000-workspace-sandbox.md`
- Stufe 2 Plan: `.hermes/plans/2026-08-18_213000-stufe-2-permission-bridge.md`
- Code: `src/eaccode/workspace.py`, `src/eaccode/tools.py`, `src/eaccode/editing.py`, `src/eaccode/git.py`, `src/eaccode/approvals_store.py`, `src/eaccode/path_security.py`
- Tests: `tests/test_workspace.py`, `tests/test_approvals.py`, `tests/test_approvals_store.py`, `tests/test_path_security.py`
