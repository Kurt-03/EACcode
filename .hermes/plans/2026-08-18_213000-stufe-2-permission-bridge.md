# Plan H.minimal v4: Stufe 2 — Permission-Bridge für Workspace-Exceptions

> **Status:** DRAFT — wartet auf User-Freigabe
> **Vorbau:** Plan H.minimal v3 (Stufe 1) ist committed (`bcf8b75`)
> **Stand:** eaccode hat Soft-Sandbox mit cwd-as-workspace. User kann nicht mehr raus.

## Was Stufe 2 löst

Stufe 1 macht `..`, absolute Pfade außerhalb cwd → blockiert. **Aber**: was wenn du **gezielt** ein Pfad raus-mappen willst?

```
> lies C:/Users/admin/Documents/notes.md
→ blocked: outside workspace

> /approvals allow-path C:/Users/admin/Documents  (once)
> lies C:/Users/admin/Documents/notes.md
→ ✓ liest Datei

> lies C:/Users/admin/Documents/notes.md  # 2. Versuch
→ blocked (war once)

> /approvals allow-path C:/Users/admin/Documents  (session)
> ... jetzt für diese Session erlaubt
```

## Was rein kommt (5 Komponenten, ~1500 LOC)

### Komponente A — `/approvals` Slash-Commands (3 commands)

`src/eaccode/commands.py` Extension:

1. **`/approvals allow-path <path> [--once|--session|--always]`** — Pfad explizit erlauben
2. **`/approvals deny-path <path> [--once|--session|--always]`** — Pfad explizit blockieren
3. **`/approvals list`** — Liste aller Allow/Deny-Regeln

### Komponente B — `Workspace.allow_paths` + `deny_paths` runtime-mutation

`src/eaccode/workspace.py` Erweiterung:
- `workspace.add_allow(path, scope)` — fügt eine Allow-Regel hinzu
- `workspace.add_deny(path, scope)` — fügt eine Deny-Regel hinzu
- `workspace.list_rules()` — zeigt alle Regeln mit scope
- Glob-Pattern support: `C:/Users/*/Documents`

### Komponente C — Persistence (scope=always)

`src/eaccode/approvals_store.py` NEU:
- `~/.local/share/eaccode/approvals.json`
- Lade bei Startup, speichere bei Änderung
- Glob-Validation

### Komponente D — Validierung mit strengeren Regeln (Hermes-Style)

`src/eaccode/workspace.py` Erweiterung:
- `validate_within_dir(path, root)` — Hermes-style strikter
- `has_traversal_component(path_str)` — explizite `..`-Erkennung
- `is_blocked_device(path)` — Windows-Device-Pfade (`C:/aux`, `NUL`, etc.)
- UNC-Pfade blocken (`\\server\share`) standardmäßig

### Komponente E — Tests (3 Test-Files, ~250 LOC)

- `tests/test_approvals.py` — 50 Tests für Slash-Commands
- `tests/test_workspace_advanced.py` — 30 Tests für Validierung
- `tests/test_approvals_store.py` — 25 Tests für Persistence

## Konfig-Format in `config.yaml`

```yaml
workspace:
  # root = Path.cwd() by default (Stufe 1)
  allow_paths:
    - "C:/Users/admin/Documents"        # Verzeichnis
    - "C:/Users/admin/Desktop/*.md"     # Glob
  deny_paths:
    - "C:/Users/admin/secrets"          # Verzeichnis
    - "C:/Users/admin/.ssh"             # Blockiert explizit
```

## Slash-Command-UX

```
$ eaccode
❯ /approvals list
Allow-paths:
  - C:/Users/admin/Documents  (session)
  - C:/Users/admin/Desktop    (always)

Deny-paths:
  - C:/Users/admin/secrets    (always)

❯ /approvals allow-path C:/Users/admin/Desktop --once
✓ Allowed C:/Users/admin/Desktop (scope: once)

❯ /approvals allow-path C:/Users/admin/Documents
✓ Allowed C:/Users/admin/Documents (scope: session)

❯ /approvals deny-path C:/Users/admin/secrets --always
✓ Denied C:/Users/admin/secrets (scope: always)
```

## 5-Option-Approval (für Mutating Tools)

Hermes hat 5 Optionen: `allow_once`, `allow_session`, `allow_always`, `deny`, `deny_always`. eaccode hat aktuell nur y/n (Plan C).

```
Tool: write_file
Action: write to C:/Users/admin/Documents/notes.md

Allow: [y] once | [s] session | [a] always | [n] deny | [A] deny_always
❯ s
```

### Zeitaufwand

| Komponente | LOC | Zeit |
|---|---|---|
| Slash-Commands | ~250 | 1 Tag |
| Runtime-Mutation | ~200 | 1 Tag |
| Persistence | ~150 | 0.5 Tag |
| Validierung | ~300 | 1 Tag |
| Tests | ~400 | 1 Tag |
| **Total** | **~1300** | **~5 Tage** |

## Reihenfolge

1. **Tag 1**: Slash-Commands (`/approvals allow-path/deny-path/list`)
2. **Tag 2**: Workspace-Runtime-Mutation (add_allow/add_deny/list_rules)
3. **Tag 3**: Persistence (approvals.json)
4. **Tag 4**: Strengere Validierung (traversal, blocked_devices, UNC)
5. **Tag 5**: Tests + Brain-Doku + Manual-Test-Anleitung

## Was du danach kannst

- `cd /path/to/myproject` → workspace = `/path/to/myproject/`
- `/approvals allow-path ~/Desktop` → jetzt kann Model Desktop lesen
- `/approvals allow-path C:/Users/*/Documents` → alle User-Verzeichnisse
- Glob-Pattern + Permission-Bridge

## Frage

Soll ich Stufe 2 jetzt starten?

**Optionen:**
- **(A)** Stufe 2 komplett (~1300 LOC, 5 Tage, alle 5 Komponenten)
- **(B)** Nur Komponente A+B (Slash-Commands + Runtime-Mutation, ~450 LOC, 2 Tage)
- **(C)** Andere Reihenfolge

Sag was.