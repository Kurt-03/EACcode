---
name: slash-palette
type: system
status: done
phase: D0.1+ (Nutzerwunsch 2026-08-13)
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Slash-Palette (Variante A)

## Zweck
`/` öffnet ein Overlay mit allen Commands **und Skills** (fuzzy gefiltert),
Pfeiltasten navigieren, Enter übernimmt/ausführt, Escape schließt — wie bei
Hermes / Claude Code.

## Implementierung
- `src/eaccode/palette.py` — prompt_toolkit-Completer (`_SlashCompleter`),
  Subsequence-Fuzzy (`fuzzy_match`), `palette_entries()` (Commands aus
  HELP_TEXT + Skills mit Trigger), `repl_prompt()`
- `repl.py` — `_input_lines()`: TTY → Palette, sonst stdin (Tests/Pipes)
- `HELP_TEXT` nach `commands.py` verschoben (Import-Zyklus vermieden)
- Dependency: `prompt_toolkit>=3`

## Verifiziert (live, 2026-08-13, PTY)
- `/` → alle Commands erscheinen (Multi-Column)
- Pfeil ↓ + Enter → `/help` übernommen und ausgeführt
- Bug gefunden+gefixt: `len<2`-Gate verhinderte das Aufklappen bei nacktem `/`

## Tests
`tests/test_palette.py` (9: Fuzzy, Entries, Completer, Slash-alone, Fallback)

## Offene Punkte
- Skills erscheinen als `/skillname` (Enter fügt Trigger ein — zweiter
  Enter sendet). Escape-Verhalten standard (schließt Overlay)
- Rückbau möglich (Nutzer-Vorbehalt): Palette-Code in palette.py isoliert

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/skill-system.md|skill-system]] · [[15-features/system/repl.md|REPL]]
