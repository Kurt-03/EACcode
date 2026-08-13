---
name: cmd-session
type: command
status: active
phase: B3
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /session

## Zweck
Session-History durchsuchen und anzeigen (SQLite + FTS5).

## Syntax
```
/session browse                  letzte 10 Sessions
/session search <begriff>        Volltextsuche in allen Sessions
/session show <session-id>       eine Session anzeigen
```
CLI-Äquivalent: `eaccode session <cmd>`

## Implementierung
- `src/eaccode/commands.py` — `run_session_command`
- `src/eaccode/store.py` — browse/search/show

## Tests
`tests/test_commands.py` (TestSessionCommands)

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/session-store.md|session-store]]
