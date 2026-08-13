---
name: read_file
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: read_file

## Zweck
Textdatei lesen (UTF-8, bis 8000 Zeichen, danach Truncation-Marker).

## Implementierung
- `src/eaccode/tools.py` — `read_file(path, max_chars)`
- Immer String-Rückgabe, nie Exceptions; Fehler als `Error: …`

## API (für das Modell)
`read_file(path: string, max_chars?: integer)`

## Tests
`tests/test_tools.py` — TestFiles (lesen, fehlend, truncate)

## Offene Punkte
- (keine)

## Verknüpft
[[../README|Feature-Register]] · [[../20-areas/architecture|Architektur]]
