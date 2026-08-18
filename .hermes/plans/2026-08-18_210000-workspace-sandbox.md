# Plan H.minimal: Isolated Workspace — 3 Stufen

> **Fokus:** Nur Block B + Minimum an Block A für Sandbox-Funktionalität.
> **Stand:** eaccode hat aktuell 0% Sandbox-Isolation.

## Was bedeutet "isolated" konkret — 3 Stufen

### Stufe 1 — Soft-Sandbox (1-2 Wochen, ~600 LOC)

**Was es macht:**
- Relative Pfade wie `./foo.py` werden in ein **virtuelles Root** umgelenkt (z.B. `.eaccode-workspace/` im cwd)
- Absolute Pfade wie `C:/Users/...` werden **automatisch in virtuelles Root gemappt** (sieht aus wie `~/foo.py` → `.eaccode-workspace/foo.py`)
- Model **sieht nicht** dass es gemappt wird — gibt einfach Pfade an wie es will
- read/write/list/search/file_edit **alle** gehen durch die Sandbox

**Was es macht (alle deine Tools, nicht nur `run_command`):**

Alle Tools die **Pfade akzeptieren** werden durch den Sandbox-Layer geschickt:

| Tool | Sandbox-Verhalten |
|---|---|
| `read_file`, `write_file` | Pfad wird in workspace gemappt |
| `list_files`, `search_files` | Nur innerhalb workspace |
| `file_edit`, `patch_file`, `patch_multiple` | Nur innerhalb workspace |
| `git_*` (status, diff, log, commit, ...) | Working-Dir wird auf workspace gemappt |
| `repo_scan`, `repo_search`, `repo_context` | Nur innerhalb workspace |
| `memory_*` | MEMORY.md bleibt in echtem Filesystem (User-Profile) |
| `create_skill`, `improve_skill` | Skills bleiben in echtem Filesystem |
| `browser_*` | Browser hat eigene Sandbox (URLs, nicht Pfade) |
| `run_command` | **Bleibt nativ** in Stufe 1 (siehe Stufe 2) |
| `http_get`, `web_search` | URLs, keine Pfade |

**Für dich:**
```
$ eaccode
> lies meine Desktop-Datei test.py
→ ERROR: cannot access /Users/admin/Desktop/test.py (outside workspace)

> schreibe test.py
→ Schreibt nach ./eaccode-workspace/test.py ✓

> git status
→ git status im workspace (nicht dein ganzes cwd)

> memory_add "User mag Pizza"
→ Speichert in echtem MEMORY.md (cross-session, persistent)
```

### Stufe 2 — Hard-Sandbox mit Permission-Bridge (2-3 Wochen, ~1500 LOC)

**Was es macht (zusätzlich zu Stufe 1):**
- `run_command` läuft auch in Sandbox (chroot/Windows-Junction-basierter Container)
- Alle Tools (read/write/edit/git/repo/etc.) checken via `validate_within_dir`
- Permission-Bridge: User kann einzelne Pfade explizit aus der Sandbox **rausmappen** (`/approvals allow-path C:/...`)
- Bei allen Tools außerhalb sandbox: explicit user-approval nötig

**Für dich:**
```
$ eaccode
> rm -rf C:/Users/admin
→ BLOCKED: outside workspace
> /approvals allow-path C:/Users/admin (once)
→ rm -rf läuft EINMAL
> rm -rf C:/Users/admin
→ BLOCKED wieder
```

### Stufe 3 — Docker-Container-Per-Task (Hermes-Verbatim, 4-6 Wochen, ~3500 LOC)

**Was es macht (zusätzlich zu Stufe 2):**
- Echtes Docker-Container statt Filesystem-Junction
- Per-Task-Image-Overrides (`python:3.11`, `node:20`)
- Sub-Agents teilen parent's Container (alias-registry)
- Cleanup-Thread räumt inactive Container auf
- Host-Path-Detection: kein `/etc`, `~/.ssh`, `~/` aus realem Filesystem

**Für dich:**
```
$ eaccode
> python -c "import os; print(os.listdir('/home/user'))"
→ listet nur sandbox-home, nicht deine echten Files
```

## Was ist VORARBEIT für Stufe 1?

**Nichts.** Stufe 1 ist ein **Filesystem-Mapping-Layer**. Kein Docker nötig.

**Vorarbeit für Stufe 2:**
- H6 Interpreter-Detection (verhindert `python -c "rm -rf"` durch sandbox escape)
- H7 Shell-Token-Parser (erkennt `$()` substitution vor sandbox)

**Vorarbeit für Stufe 3:**
- Alles aus Stufe 2
- H13 Task-Env-Overrides (welches Image für welchen Task)
- H14 Container-Aliasing (Sub-Agents teilen parent's Container)
- H17 Docker-Volume-Host-Path-Detection (Sandbox-Escape verhindern)

## Empfehlung

**Stufe 1 (1-2 Wochen) ist das was du brauchst.** Es löst das Kern-Problem:

> eaccode sieht alle Pfade im Filesystem, kein Sandbox

Mit Stufe 1 sieht eaccode nur:
- Relative Pfade innerhalb cwd (`.eaccode-workspace/`)
- Keine `C:/Users/admin/...` mehr
- `~/` → cwd-internes Verzeichnis
- `..` → blockiert (Path-Traversal-Schutz)

**Stufe 1 commit-by-commit:**
1. **Workspace-Root-Detection** (welcher Pfad ist "unser" Workspace?)
2. **Path-Rewriting-Layer** (`/foo.py` → `<workspace>/foo.py`, `/etc/passwd` → ERROR)
3. **Tools-Integration** (alle read/write/edit-Tools nutzen Rewriter)
4. **Permission-Bridge** (User kann Pfade explizit raus-mappen)
5. **Path-Traversal-Schutz** (`..` wird gefangen)
6. **Symlink-Schutz** (Symlinks können sandbox-escapen, daher resolved-then-check)

## Wieviel Code ist das?

| Hermes-Funktion | LOC | Was |
|---|---|---|
| `_expand_tilde` | 35 | `~` → home |
| `_resolve_path` | 20 | Path.resolve |
| `_uses_container_paths` | 12 | Check container vs host |
| `_normalize_without_host_deref` | 10 | Pure-PosixPath |
| `_sentinel_free_abs_cwd` | 17 | Sentinel-Handling |
| `_configured_terminal_cwd` | 12 | cwd config |
| `_registered_task_cwd_override` | 18 | Task-Override |
| `_authoritative_workspace_root` | 35 | Root-Detection |
| `_resolve_base_dir` | 60 | Base-Dir-Resolution |
| `_resolve_path_for_task` | 38 | Path-Resolve pro Task |
| `_path_resolution_warning` | 40 | Warnungen |
| `_file_ops_uses_host_paths` | 18 | Host-Path-Check |
| `_rewrite_v4a_patch_paths_for_host` | 60 | Patch-Path-Rewrite |
| `_is_blocked_device_path` | 35 | Device-Path-Check |
| `_is_blocked_device` | 40 | Device-Block |
| `_search_result_read_block_error` | 15 | Read-Block-Error |
| `_filter_read_blocked_search_results` | 15 | Filter |
| ... | ... | ... |
| **Total Hermes file_tools.py** | **2673** | **Sandbox-Pfad-Logik** |

**Für eaccode Stufe 1 (Soft-Sandbox):**
- Workspace-Root-Detection: ~50 LOC
- Path-Rewriting: ~100 LOC
- Tool-Integration: ~150 LOC (Hooks in read/write/edit/list/search)
- Permission-Bridge: ~100 LOC
- Path-Traversal-Schutz: ~50 LOC
- Symlink-Schutz: ~30 LOC
- Tests: ~150 Tests, ~400 LOC
- **Total: ~880 LOC** in ~1-2 Wochen

## Plan

**Sprint-Welle H.minimal (1-2 Wochen, ~880 LOC):**

1. **Tag 1-2**: Workspace-Root-Detection
   - `src/eaccode/workspace.py` NEU
   - `is_path_in_workspace(path, workspace_root)` 
   - `get_workspace_root()` — cwd + `.eaccode-workspace/`
   - Tests

2. **Tag 3-4**: Path-Rewriting-Layer
   - `rewrite_path(path, workspace_root)` — alle Tools
   - `validate_path(path)` — keine `..`, kein absoluter Pfad außerhalb
   - Tests für relative/absolute/tilde/parent-traversal

3. **Tag 5-6**: Tool-Integration
   - `read_file`, `write_file`, `list_files`, `search_files`, `file_edit`, `patch_file` — alle durch Rewriter
   - `git_*` — Working-Dir wird auch rewritten
   - Tests für jeden Tool

4. **Tag 7-8**: Permission-Bridge
   - `eaccode permissions.allow_paths` config-Feld
   - `is_path_allowed(path, allow_paths)` 
   - User kann Pfade explizit raus-mappen
   - Tests

5. **Tag 9-10**: Symlink + Edge-Cases
   - `resolve_and_validate(path)` — `Path.resolve()` + `relative_to(workspace_root)` 
   - Tests für Symlink-Attacks, UNC-Pfade, etc.

## Live-Verifikation nach Stufe 1

```
$ cd /path/to/myproject
$ eaccode

> liest Desktop-Datei test.py
→ ERROR: cannot access /Users/admin/Desktop/test.py (outside workspace)

> schreibe foo.py
→ Schreibt nach /path/to/myproject/.eaccode-workspace/foo.py ✓

> liste Dateien
→ listet .eaccode-workspace/ — nicht deinen ganzen cwd

> cat ../secrets.txt
→ ERROR: path-traversal blocked

> /approvals allow-path /Users/admin/Desktop
→ ab jetzt kann Model dort lesen/schreiben

> rm -rf ../important.txt
→ ERROR: outside workspace (auch run_command würde blockiert)
```

## Was es **nicht** macht (Stufe 1)

- **`run_command` läuft noch nativ** (echtes Filesystem, kein chroot/junction)
- **Docker wird nicht benutzt** (kein Container-Per-Task)
- **Per-Task-Image-Selection nicht** (kein Python:3.11 vs Python:3.12)
- **Sub-Agent-Sandbox-Isolation nicht** (Sub-Agents teilen parent's Sandbox)
- **Memory/Skill-Pfade ausgenommen** (MEMORY.md, Skills bleiben im echten Profile-Verzeichnis, weil sie cross-session persistent sind)

Diese sind Stufe 2 und 3.

## Frage

**Stufe 1 (1-2 Wochen Soft-Sandbox) jetzt umsetzen?**

Oder willst du erst Stufe 2 oder 3 direkt?

Oder ist Stufe 1 + Stufe 2 (= Hard-Sandbox mit Permission-Bridge) das was du brauchst?

Sag was.
