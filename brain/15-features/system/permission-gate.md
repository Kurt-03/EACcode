---
name: permission-gate
type: system
status: done
phase: A5/C1
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Permission-Gate (A5 → C1 abgelöst)

> **Hinweis:** Seit C1 ist [[15-features/system/permissions.md|permissions]]
> die zentrale Instanz (PermissionManager für ALLE Tools). Diese Notiz
> dokumentiert den A5-Ursprung (Terminal-Gate) als Historie.

# System: Permission-Gate

## Zweck
Shell-Kommandos des Agents brauchen Zustimmung — sicherer Default.

## Implementierung (Phase A)
- `src/eaccode/tools.py` — Modul-Level `permission_handler` (Default: Deny)
- REPL verdrahtet interaktiven Prompt: `Allow: <cmd> [y/N]`
- TUI: aktuell Deny (sicher, aber ohne Prompt)

## Tests
`tests/test_tools.py` (TestTerminal) + REPL-Permission-Verdrahtung

## Offene Punkte (C1 — volles System)
- Regelbasiert (Auto-Approve für bestimmte Kommandos/Verzeichnisse)
- Plan-/Read-only-Modus
- Sandbox (Docker optional; Windows-sicher)
- TUI-Prompt (Modal)

## Verknüpft
[[15-features/README.md|Feature-Register]] · *Tool `run_command` ist seit 08-18 entfernt (Plan H)*
