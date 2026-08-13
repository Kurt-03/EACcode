---
name: cmd-help
type: command
status: done
phase: A1
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /help

## Zweck
Zeigt die Übersicht aller Slash-Commands in der Session.

## Syntax
```
/help
```

## Implementierung
- `src/eaccode/repl.py` — `HELP_TEXT`, Dispatch in `_handle_command`
- TUI: gleiche Hilfe via `/help` im Input (Log-Ausgabe)

## Tests
`tests/test_repl.py` — `/help` zeigt Command-Liste

## Verknüpft
[[15-features/commands/README.md|README]]
