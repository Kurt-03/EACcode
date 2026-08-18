---
name: 0005-workspace-sandbox
type: ADR
status: accepted
date: 2026-08-18
tags: [type/adr, feature/architecture, workspace, sandbox, hermes]
---

# ADR-0005: Workspace-Sandbox (Plan H.minimal)

## Kontext

eaccode hatte keine Filesystem-Isolation. Das Model konnte mit absoluten
Pfaden jeden Pfad im System erreichen (`C:/Users/admin/secret.txt`,
`~/.ssh/id_rsa`, etc.). Hermes hat eine 5-Stufen-Isolation
(`file_tools.py` 2673 Zeilen).

## Entscheidung

Plan H.minimal v3-v5: 3 Stufen

### Stufe 1 (committed `bcf8b75`) — Soft-Sandbox

- `cwd` ist workspace-root
- `..`, absolute Pfade außerhalb cwd, blocked_devices, UNC → blockiert
- Memory/Skills/Telegram-config bleiben exempt
- Hermes-Style tilde-expansion, search-result-filter

### Stufe 2 (committed `a30654b`) — Permission-Bridge

- `/approvals allow-path/deny-path [--once|--session|--always]`
- Glob-Pattern, persistent in `~/.local/share/eaccode/approvals.json`
- Hermes-Style strict validation: path_security.py
- `~/.local/share/eaccode/approvals.json` für always-scoped

### Stufe 2+ (write_approval) — Stage-Approval

- Hermes-Verbatim analog von `tools/write_approval.py`
- Memory + Skill writes gehen in `pending/<subsystem>/<id>.json`
- User review via `/memory pending` (geplant)

### Stufe 3 (Plan H v5) — Container-Backend

- Docker-Container-Per-Task (`container.py`)
- Host-Path-Detection (`.ssh`, `.aws`, `~/.gnupg`, `/etc`, `/var`)
- Cleanup-Thread für inactive Container
- Opt-in via `workspace.mode = "container"`

## Konsequenzen

**Positiv:**
- Model kann nicht mehr unkontrolliert Files lesen/schreiben
- User hat explizite `/approvals` Bridge für gezielte Pfad-Exceptions
- Memory/Skills writes gehen durch User-Review (Stage-Approval)
- Container-Optional für zusätzliche Isolation

**Negativ:**
- Stage-Approval braucht `/memory pending apply` und `/skills pending apply` Slash-Commands (noch nicht implementiert)
- Container-Backend erfordert Docker installiert (nicht überall verfügbar)
- Workspace-Mode kann nicht zur Laufzeit gewechselt werden ohne Restart

## Endstand

- 984 Tests grün
- 5 neue Module: workspace, path_security, approvals_store, write_approval, container
- Hermes-Coverage für Workspace-Bereich: 13% → ~70%

## Siehe auch

- Plan: `.hermes/plans/2026-08-18_210000-workspace-sandbox.md`
- Code: `src/eaccode/workspace.py`, `path_security.py`, `approvals_store.py`, `write_approval.py`, `container.py`