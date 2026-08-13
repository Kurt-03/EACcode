---
name: cmd-exit
type: command
status: done
phase: A1
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /exit

## Zweck
Beendet die Session sauber: gibt `bye` aus, Exit-Code 0. Alias: `/quit`.
Auch EOF (Ctrl+Z/Ctrl+D) und Ctrl+C beenden sauber.

## Syntax
```
/exit
/quit
```

## Implementierung
- `src/eaccode/repl.py` — `_handle_command` liefert Exit-Code → `bye` + return
- KeyboardInterrupt/EOF → gleicher sauberer Pfad

## Tests
`tests/test_repl.py` — Exit 0, `bye` im Output

## Verknüpft
[[15-features/commands/README.md|README]]
