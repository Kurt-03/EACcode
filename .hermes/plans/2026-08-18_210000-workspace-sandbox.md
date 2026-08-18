# Plan H.minimal v2: Isolated Workspace — 3 Stufen (run_command raus)

> **Fokus:** Workspace-Isolation für **eaccode-Tools** (write_file, file_edit, etc.).
> **Vergleichsbasis:** Claude Code (seatbelt), OpenCode (worktree), Hermes (Docker).
> **Stand:** eaccode hat aktuell 0% Sandbox-Isolation.

## Was bedeutet "isolated" konkret — 3 Stufen

### Stufe 1 — Soft-Sandbox (1-2 Wochen, ~880 LOC)

**Was es macht:**
- Workspace-Root = `<cwd>/.eaccode-workspace/` (oder vom User in config setzbar)
- Alle Pfad-Tools werden durch `rewrite_path(path)` geschickt
- Relative Pfade (`foo.py`, `./foo/bar`) bleiben im workspace
- `~/...` wird zu `<workspace>/...` gemappt
- Absolute Pfade (`C:/...`, `/home/...`) außerhalb workspace → **ERROR**
- `..` (Path-Traversal) → **ERROR**
- Symlinks → werden resolved + dann geprüft

**Sandbox-Targets (alle deine Tools, nicht `run_command`):**

| Tool | Sandbox-Verhalten |
|---|---|
| `read_file`, `write_file` | Pfad wird in workspace gemappt |
| `list_files`, `search_files` | Nur innerhalb workspace |
| `file_edit`, `patch_file`, `patch_multiple`, `undo_edit` | Nur innerhalb workspace |
| `git_*` (status, diff, log, commit) | Working-Dir wird auf workspace gemappt |
| `repo_scan`, `repo_search`, `repo_context` | Nur innerhalb workspace |
| `memory_*` | Bleibt in echtem `MEMORY.md` (cross-session) |
| `create_skill`, `improve_skill` | Bleibt in echtem Skills-Verzeichnis |
| `browser_*` | Hat eigene Sandbox (URLs, nicht Pfade) |
| `http_get`, `web_search` | URLs, keine Pfade |

**Für dich:**
```
$ cd /path/to/myproject
$ eaccode

> lies Desktop-Datei test.py
→ ERROR: cannot access /Users/admin/Desktop/test.py (outside workspace)

> schreibe test.py
→ Schreibt nach /path/to/myproject/.eaccode-workspace/test.py ✓

> git status
→ git status im workspace (nicht dein ganzes cwd)

> memory_add "User mag Pizza"
→ Speichert in echtem MEMORY.md (cross-session, persistent)

> cat ../secrets.txt
→ ERROR: path-traversal blocked
```

**Was es NICHT macht:**
- `run_command` ist **kein** Sandbox-Target (User-Wunsch)
- **Docker wird nicht benutzt** (kein Container-Per-Task)
- **Per-Task-Image-Selection nicht**
- **Sub-Agent-Sandbox-Isolation nicht**

---

### Stufe 2 — Permission-Bridge für Workspace-Exceptions (2-3 Wochen, ~1500 LOC)

**Was es macht (zusätzlich zu Stufe 1):**
- User kann **explizit Pfade** aus der Sandbox **rausmappen**
- `/approvals allow-path C:/Users/admin/Desktop` → einmalig
- `/approvals allow-path C:/Users/admin/Desktop` mit `session` → für Session
- `/approvals allow-path C:/Users/admin/Desktop` mit `always` → permanent
- `/approvals deny-path ...` → blockiert immer
- Glob-Pattern: `/approvals allow-path C:/Users/*/Documents`
- `validate_within_dir(path)` mit strengeren Regeln (Hermes-style)

**Für dich:**
```
$ eaccode

> rm C:/Users/admin/Desktop/important.txt
→ BLOCKED: outside workspace
> /approvals allow-path C:/Users/admin/Desktop (once)
> rm C:/Users/admin/Desktop/important.txt
→ Läuft EINMAL
> rm C:/Users/admin/Desktop/important.txt
→ BLOCKED wieder (war einmalig)
```

**Permission-Konfiguration in config.yaml:**
```yaml
permissions:
  workspace_root: .eaccode-workspace/   # Default
  allow_paths:
    - C:/Users/admin/Desktop          # Immer erlaubt
    - C:/Users/admin/Documents/*.md   # Glob
  deny_paths:
    - C:/Users/admin/secrets/         # Immer blockiert
```

---

### Stufe 3 — Docker-Container-Per-Task (Hermes-Verbatim, 4-6 Wochen, ~3500 LOC)

**Was es macht (zusätzlich zu Stufe 2):**
- Echtes Docker-Container statt Filesystem-Mapping
- Per-Task-Image-Overrides (`python:3.11`, `node:20`, `rust:1.75`)
- Sub-Agents teilen parent's Container (alias-registry)
- Cleanup-Thread räumt inactive Container auf (default 5min)
- Host-Path-Detection: kein `/etc`, `~/.ssh`, `~/` aus realem Filesystem
- `run_command` läuft auch im Container (opt-in)

**Für dich:**
```
$ eaccode

> python -c "import os; print(os.listdir('/home/user'))"
→ listet nur sandbox-home, NICHT deine echten Files

> Sub-Agent mit Python 3.11
→ eigener Container mit python:3.11
→ Cleanup nach 5min Inaktivität

> run_command rm -rf /  # opt-in Container
→ Container-FS, nicht dein Host-FS
```

---

## Hermes-Vergleich (was wir NICHT 1:1 kopieren)

| Hermes | eaccode Stufe 1 | Stufe 2 | Stufe 3 |
|---|---|---|---|
| Container-Per-Task | ❌ | ❌ | ✅ |
| Filesystem-Root-Mapping | ✅ | ✅ | ✅ (via Container) |
| Glob allow_paths | ❌ | ✅ | ✅ |
| Symlink-Schutz | ✅ | ✅ | ✅ (Container-isolation) |
| Path-Traversal-Block | ✅ | ✅ | ✅ |
| Per-Session-Isolation | ❌ | ✅ | ✅ |
| Docker-Volume-Detect | ❌ | ❌ | ✅ |
| Image-Overrides | ❌ | ❌ | ✅ |
| Cleanup-Thread | � | ❌ | ✅ |
| ACLs per File | ❌ | ❌ | � (out of scope) |

---

## Was ist VORARBEIT für Stufe 1?

**Nichts.** Stufe 1 ist ein **Filesystem-Mapping-Layer**. Kein Docker, kein Interpreter-Detection nötig.

**Vorarbeit für Stufe 2:** Nichts (alles in Stufe 1 gebaut).

**Vorarbeit für Stufe 3 (Docker-Container):**
- **H6** Interpreter-Detection (verhindert `python -c "rm -rf"` als Sandbox-Escape)
- **H7** Shell-Token-Parser (erkennt `$()` substitution)
- **H17** Docker-Volume-Host-Path-Detection (Sandbox-Escape-Prevention)
- **H13** Task-Env-Overrides (welches Image für welchen Task)

---

## Was ist mit `run_command`?

**`run_command` ist KEIN eaccode-Tool** (User-Wunsch — Kurt sieht es nicht als "echtes Tool"). In allen Stufen:
- Stufe 1: nativ (kein Sandbox-Target)
- Stufe 2: nativ (mit Permission-Bridge auch für run_command möglich)
- Stufe 3: nativ ODER opt-in in Docker-Container

**Für Sandbox-Isolation ist `run_command` NICHT relevant.**

---

## Sprint-Welle H.minimal — Empfehlung

**Stufe 1 jetzt (~880 LOC, 1-2 Wochen):**

### Tag 1-2: Workspace-Root-Detection

`src/eaccode/workspace.py` NEU:
- `Workspace` dataclass: `root`, `mode` (soft/hard/container)
- `get_workspace_root()` — cwd + `.eaccode-workspace/`
- `set_workspace_root(path)` — User-Override via config

### Tag 3-4: Path-Rewriting-Layer

`src/eaccode/workspace.py`:
- `rewrite_path(path, workspace)` — alle Path-Inputs
- `validate_path(path, workspace)` — keine `..`, kein absoluter Pfad außerhalb
- `is_in_workspace(path, workspace)` — `Path.resolve().relative_to(workspace_root)`

### Tag 5-6: Tool-Integration

`src/eaccode/tools.py`, `editing.py`, `git.py`, `repo.py`:
- read_file, write_file, list_files, search_files, file_edit, patch_file, patch_multiple, undo_edit → durch Rewriter
- git_* → Working-Dir = workspace
- repo_scan, repo_search, repo_context → durch Rewriter

### Tag 7-8: Path-Traversal + Symlink-Schutz

- `resolve_and_validate(path)` — `Path.resolve(strict=False)` + `relative_to(workspace_root)`
- Blockiere Symlinks die aus workspace raus zeigen
- UNC-Pfade blocken

### Tag 9-10: Tests + Doku

- 30+ Tests für Path-Rewriting
- 20+ Tests für Tool-Integration
- Brain-Doku: `workspace.md`
- Manual-Test in `docs/manual-test.md`

**Total:** ~880 LOC, ~150 Tests

---

## Live-Verifikation nach Stufe 1

```
$ cd /path/to/myproject
$ eaccode

> liest Desktop-Datei test.py
→ ERROR: cannot access /Users/admin/Desktop/test.py (outside workspace)

> schreibe test.py
→ Schreibt nach /path/to/myproject/.eaccode-workspace/test.py ✓

> liste Dateien
→ listet .eaccode-workspace/ — nicht deinen ganzen cwd

> cat ../secrets.txt
→ ERROR: path-traversal blocked

> rm -rf /
→ ERROR: hardline blocked (Plan D)

> /approvals allow-path /Users/admin/Desktop (Stufe 2)
→ ab jetzt kann Model dort lesen/schreiben

> git status
→ git status im workspace (nicht dein ganzes cwd)
```

---

## Frage an User

**Soll ich Stufe 1 jetzt umsetzen?**
- ~880 LOC, ~150 Tests, 1-2 Wochen
- Commits: 5-7 (je Phase)
- Brain-Update + Manual-Test-Anleitung

Sag ja oder ändere die Priorisierung.
