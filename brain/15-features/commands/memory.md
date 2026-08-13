---
name: cmd-memory
type: command
status: done
phase: A6
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /memory

## Zweck
Persistente Memory verwalten (MEMORY.md / USER.md).

## Syntax
```
/memory show                MEMORY.md + USER.md (als Injection-Block)
/memory add <text>          Fakt an MEMORY.md anhängen
/memory user add <text>     Fakt an USER.md anhängen
/memory remove <substring>  Einträge mit Substring entfernen
```
CLI-Äquivalent: `eaccode memory <cmd>`

## Implementierung
- `src/eaccode/commands.py` — `run_memory_command`
- `src/eaccode/memory.py` — add/remove/injection_text

## Tests
`tests/test_commands.py` (TestMemoryCommands) + `tests/test_memory.py`

## Offene Punkte
- B4: Agent-Tools + Char-Budgets + apply_batch (Hermes-Modell) ersetzen/ergänzen
  die reinen User-Kommandos

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/memory.md|Memory]]
