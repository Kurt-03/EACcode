---
name: list_files
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: list_files

## Zweck
Verzeichnisinhalt auflisten (Verzeichnisse mit `/`-Suffix, alphabetisch).

## Implementierung
- `src/eaccode/tools.py` — `list_files(path=".")`

## API
`list_files(path?: string)`

## Tests
`tests/test_tools.py` — TestFiles (Inhalt, Unterordner-Marker)

## Verknüpft
[[15-features/README.md|Feature-Register]]
