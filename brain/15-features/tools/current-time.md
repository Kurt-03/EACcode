---
name: current_time
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: current_time

## Zweck
Aktuelle lokale Zeit (`YYYY-MM-DD HH:MM:SS`) — wichtig für zeitbezogene
Agent-Aufgaben.

## Implementierung
- `src/eaccode/tools.py` — `current_time()` via `datetime.now()`

## Tests
`tests/test_tools.py` — Format-Länge 19

## Verknüpft
[[15-features/README.md|Feature-Register]]
