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

## Endstand

- 896 Tests grün
- ~1050 LOC neu (workspace + sandboxing)
- 23 workspace-tests + bestehende Tests angepasst

## Reference

- Plan: `.hermes/plans/2026-08-18_210000-workspace-sandbox.md`
- Code: `src/eaccode/workspace.py`, `src/eaccode/tools.py`, `src/eaccode/editing.py`, `src/eaccode/git.py`
- Tests: `tests/test_workspace.py`
