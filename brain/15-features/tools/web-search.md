---
name: web_search
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: web_search

## Zweck
Web-Suche (DuckDuckGo HTML) — liefert Titel + URL je Treffer.

## Implementierung
- `src/eaccode/tools.py` — `web_search(query, max_results)` + DDG-Parser
- Bewusst ohne API-Key (BYOK-freundlich); HTML-Suche ist fragil

## API
`web_search(query: string, max_results?: integer)`

## Tests
`tests/test_tools.py` — Parse, keine Treffer, Fehler

## Offene Punkte
- DDG-HTML kann sich ändern → robusteren Endpunkt/API evaluieren (Research)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[30-research/README.md|Research]]
