---
name: cmd-version
type: command
status: done
phase: A1
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /version

## Zweck
Zeigt die eaccode-Version (aktuell `0.0.1` — dauerhaft).

## Syntax
```
/version
```
CLI-Äquivalent: `eaccode --version`

## Implementierung
- `src/eaccode/repl.py` — `_handle_command` → `eaccode {__version__}`
- `src/eaccode/cli.py` — `--version`-Flag

## Tests
`tests/test_repl.py` + `tests/test_cli.py` — Version 0.0.1

## Verknüpft
[[15-features/commands/README.md|README]]
