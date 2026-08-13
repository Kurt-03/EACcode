---
name: write_file
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: write_file

## Zweck
Text in Datei schreiben; legt Eltern-Verzeichnisse automatisch an.

## Implementierung
- `src/eaccode/tools.py` — `write_file(path, content)`
- Bestätigung `written N chars to <path>`

## API
`write_file(path: string, content: string)`

## Tests
`tests/test_tools.py` — write erstellt Eltern-Verzeichnisse

## Offene Punkte
- (keine)

## Verknüpft
[[15-features/README.md|Feature-Register]]
