---
name: tools-layer
type: system
status: done
phase: A5
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Tools-Layer (tools.py)

## Zweck
Zentrales Modul mit allen Basis-Tools für den Agenten: Dateien, Terminal,
Web, Info. Jedes Tool hat eine eigene Notiz (siehe Register).

## Implementierung
- `src/eaccode/tools.py` — `BUILTIN_TOOLS` (9 Tools), `permission_handler`
- Alle Tools liefern Strings, werfen nie; Permission-Gate für `run_command`
- Tools: [[15-features/tools/read-file.md|Tool: read_file]] · [[15-features/tools/write-file.md|Tool: write_file]] · [[15-features/tools/list-files.md|Tool: list_files]] · [[15-features/tools/search-files.md|Tool: search_files]] · *(`run_command` entfernt 08-18, Plan H)* · [[15-features/tools/http-get.md|Tool: http_get]] · [[15-features/tools/web-search.md|Tool: web_search]] · [[15-features/tools/current-time.md|Tool: current_time]] · [[15-features/tools/system-info.md|Tool: system_info]]

## Tests
`tests/test_tools.py` + Integration über Agent-Loop-Tests

## Offene Punkte
- D1: `search_files` auf Ripgrep + `.gitignore`-Respekt umstellen
- Browser-Tool (D6) kommt als eigenes Feature

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/permission-gate.md|Permission-Gate]]

## Code-Graph (generiert)

- `src/eaccode/tools.py` → [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/workspace.md|workspace]]

