---
name: system_info
type: tool
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/tool]
---

# Tool: system_info

## Zweck
Betriebssystem- und Hardware-Kurzinfo (OS, Release, Architektur).

## Implementierung
- `src/eaccode/tools.py` — `system_info()` via `platform`

## Tests
`tests/test_tools.py` — nicht leer

## Verknüpft
[[../README|Feature-Register]]
