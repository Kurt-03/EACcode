---
name: search_files
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: search_files

## Zweck
Dateien finden, deren Text ein Muster enthält (rekursiv, max. 50 Treffer).

## Implementierung
- `src/eaccode/tools.py` — `search_files(pattern, path=".")`
- Einfache Substring-Suche (kein Regex) — bewusst simpel für Phase A

## API
`search_files(pattern: string, path?: string)`

## Tests
`tests/test_tools.py` — findet über Unterordner, "no matches"

## Offene Punkte
- D1 (Repo-Verständnis): Ripgrep-basiert + `.gitignore`-Respekt statt rglob

## Verknüpft
[[15-features/README.md|Feature-Register]]
