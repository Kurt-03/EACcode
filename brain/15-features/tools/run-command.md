---
name: run_command
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: run_command

## Zweck
Shell-Kommando ausführen — **immer durch das Permission-Gate** (y/N in der
REPL, Default-Deny).

## Implementierung
- `src/eaccode/tools.py` — `run_command(command, cwd, timeout)` +
  Modul-Level `permission_handler`
- Exit-Code ≠ 0 wird als `(exit N)` angehängt; Timeout → saubere Meldung

## API
`run_command(command: string, cwd?: string, timeout?: integer)`

## Tests
`tests/test_tools.py` — deny default, allow, Handler erhält Command, Timeout

## Offene Punkte
- C1: Regelbasiertes Permission-System (Auto-Approve, Plan-Modus, Sandbox)
- TUI: aktuell Deny (kein interaktiver Prompt im Skelett)

## Verknüpft
[[../README|Feature-Register]] · [[permission-gate|Permission-Gate]]
