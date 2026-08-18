# Plan H.minimal v3: Stufe 1 + run_command komplett raus

> **Aufgabe:**
> 1. **Stufe 1** umsetzen (Soft-Sandbox für eaccode-Tools, ~880 LOC)
> 2. **`run_command` komplett aus eaccode entfernen** (nicht nur Sandbox-Scope)
>
> **Stand:** eaccode hat 0% Sandbox-Isolation + `run_command` als Legacy-Tool.

## Plan

### Phase 1 — `run_command` raus (Tag 1, ~200 LOC)

**Entferne `run_command` komplett:**
- `src/eaccode/tools.py` Z. 95-310 — `run_command` Tool-Definition löschen
- `src/eaccode/tools.py` Z. 40-310 — `run_command` Handler löschen
- `src/eaccode/agent.py` — `run_command` aus System-Prompt-Workflow-Patterns raus
- `src/eaccode/cli.py` — keine Sonderbehandlung für `run_command`
- Tests: `tests/test_tools.py::TestRunCommand*` — löschen oder umschreiben
- Brain: `brain/15-features/tools/run_command.md` — löschen

**Was passiert stattdessen mit Shell-Befehlen?**
- User tippt sie **selbst** im Terminal
- `run_command` ist kein "convenience"-Tool, das das Model nutzt
- Wenn Model Shell braucht: User führt es aus mit dem Befehl den Model vorschlägt

### Phase 2 — Workspace-Root-Detection (Tag 2, ~150 LOC)

`src/eaccode/workspace.py` NEU:
- `Workspace` dataclass: `root`, `mode` ("soft" | "hard")
- `get_workspace_root()` — `cwd / .eaccode-workspace/` (Default)
- `set_workspace_root(path)` — User-Override via config
- `WorkspaceConfig` — Lade/Validierung aus config.yaml

### Phase 3 — Path-Rewriting-Layer (Tag 3, ~200 LOC)

`src/eaccode/workspace.py`:
- `rewrite_path(path, workspace)` — alle Path-Inputs
- `validate_path(path, workspace)` — keine `..`, kein absoluter Pfad außerhalb
- `is_in_workspace(path, workspace)` — `Path.resolve().relative_to(workspace_root)`
- `resolve_and_validate(path, workspace)` — Symlink-Schutz

### Phase 4 — Tool-Integration (Tag 4-5, ~300 LOC)

`src/eaccode/tools.py`, `editing.py`, `git.py`, `repo.py`:
- `read_file`, `write_file`, `list_files`, `search_files` → durch Rewriter
- `file_edit`, `patch_file`, `patch_multiple`, `undo_edit` → durch Rewriter
- `git_*` → Working-Dir = workspace
- `repo_scan`, `repo_search`, `repo_context` → durch Rewriter
- Memory/Skills bleiben **außerhalb** workspace

### Phase 5 — Tests + Doku (Tag 6-7, ~400 LOC)

- 30+ Tests für Path-Rewriting
- 20+ Tests für Tool-Integration
- 10+ Tests für Workspace-Config
- Brain-Doku: `brain/15-features/system/workspace.md`
- Manual-Test in `docs/manual-test.md`

**Total:** ~1250 LOC, ~150 Tests (Stufe 1) + ~200 LOC für `run_command` removal

---

## Sandbox-Targets (nur eaccode-Tools)

| Tool | Sandbox-Verhalten |
|---|---|
| `read_file`, `write_file` | Pfad in workspace gemappt |
| `list_files`, `search_files` | Nur innerhalb workspace |
| `file_edit`, `patch_file`, `patch_multiple`, `undo_edit` | Nur innerhalb workspace |
| `git_*` | Working-Dir = workspace |
| `repo_scan`, `repo_search`, `repo_context` | Nur innerhalb workspace |
| `memory_*` | Bleibt in echter MEMORY.md |
| `create_skill`, `improve_skill` | Bleibt in echter Skills |
| `http_get`, `web_search` | URLs |

**`run_command` ist nicht in der Liste** — Tool wird entfernt.

---

## Live-Verifikation nach Stufe 1

```
$ cd /path/to/myproject
$ eaccode

> lies Desktop-Datei test.py
→ ERROR: cannot access /Users/admin/Desktop/test.py (outside workspace)

> schreibe test.py
→ Schreibt nach /path/to/myproject/.eaccode-workspace/test.py ✓

> liste Dateien
→ listet .eaccode-workspace/

> cat ../secrets.txt
→ ERROR: path-traversal blocked

> rm -rf C:/
→ ERROR: file_safety blocked (Plan D)

> führe 'git status' aus
→ ERROR: run_command was removed - execute git status yourself in your terminal
→ git status im workspace
```

**Der letzte Punkt** zeigt das neue Verhalten: Wenn Model Shell braucht, sagt es dem User es **selbst** zu tippen. Kein Tool-Call mehr.

---

## Frage

**Alles klar?** Ich fange dann mit Phase 1 (`run_command` raus) + Phase 2-5 (Stufe 1 Sandbox) an.

Soll ich loslegen?
