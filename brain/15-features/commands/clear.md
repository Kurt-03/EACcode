---
name: cmd-clear
type: command
status: done
phase: A7
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /clear

## Zweck
Leert den Bildschirm (TTY: ANSI-Escape) **und** die Chat-History des Agenten.

## Syntax
```
/clear
```

## Implementierung
- `src/eaccode/repl.py` — `_clear_screen` (nur bei TTY) + `chat_history.clear()`
- TUI: `/clear` resetet Log + History (`tui.py`)

## Tests
`tests/test_repl.py` — History nach /clear leer; `tests/test_tui.py` — Log leer

## Verknüpft
[[15-features/commands/README.md|README]]
