---
name: memory
type: system
status: done
phase: A6
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Memory (MEMORY.md / USER.md)

## Zweck
Persistente, kuratierte Fakten über Sessions hinweg — der Unterschied zu
„normalen" Agents.

## Implementierung
- `src/eaccode/memory.py` — MEMORY.md/USER.md im Datenverzeichnis,
  `add_entry` / `remove_entry` / `injection_text`
- Injection in den System-Prompt beim Agent-Aufbau (REPL + TUI + `-p`)
- Kommandos: `/memory show|add|remove|user add`

## Kommandos
```
/memory add <fakt>        → MEMORY.md
/memory user add <fakt>   → USER.md
/memory remove <substring>
```

## Tests
`tests/test_memory.py` + `tests/test_commands.py` (TestMemoryCommands) +
REPL-Chat-Tests

## Offene Punkte
- B4: Memory-Hierarchie (global vs. projektbezogen), Char-Budget,
  Batch-Kuration, Konflikte
- B3: Session-Store (FTS5) — dann kann der Agent alte Sessions durchsuchen

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[20-areas/architecture.md|Architektur]]
