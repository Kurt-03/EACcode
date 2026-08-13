---
name: http_get
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: http_get

## Zweck
URL abrufen und Text-Inhalt zurückgeben (max. 8000 Zeichen, Timeout 15 s).

## Implementierung
- `src/eaccode/tools.py` — `http_get(url, max_chars)` via `urllib.request`
- Keine externe Dependency nötig

## API
`http_get(url: string, max_chars?: integer)`

## Tests
`tests/test_tools.py` — Fake-Response, Fehlerpfad

## Offene Punkte
- (keine) — Browser-Automatisierung kommt als eigenes Feature (D6)

## Verknüpft
[[15-features/README.md|Feature-Register]]
