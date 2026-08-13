---
name: repo-understanding
type: system
status: done
phase: D1
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Repo-Verständnis (D1)

## Zweck
Der Agent versteht Projektstrukturen: Struktur-Index mit `.gitignore`-Respekt,
rekursive Suche, Context-Packs (Modul + zugehörige Tests gebündelt).

## Implementierung
- `src/eaccode/repo.py` — `scan()` (Index: Dateien/Dirs/Größen, Grenzen:
  max. 2000 Dateien, Tiefe 12, Truncation-Marker), `search()` (Regex,
  Dateityp-Filter, `.gitignore`-Respekt, max. 50 Treffer), `context_pack()`
  (Modul + Tests + Größen + erste 40 Zeilen), `.gitignore`-Parser
  (Glob/`**`/Negation `!`; `\z`-Kompatibilität Python ≥ 3.14)
- Agent-Tools: `repo_scan`, `repo_search`, `repo_context` — read-only
  (laufen frei im ask-Modus)

## Verifiziert (live, 2026-08-13 — Hermes-Repo `C:\Projekte\_ref\hermes`)
- `repo_scan`: 2000 Dateien, 34,86 MB, sortierte Ausgabe, Truncation korrekt
- `repo_search "turns_since_memory"`: 8 Treffer, .py-Filter
- `repo_context agent/memory_manager.py`: Größe/Zeilen/Docstring/Imports;
  Agent verknüpfte Fundstellen intelligent (Nudge-Logik in turn_context.py)

## Tests
`tests/test_repo.py` (18: IgnoreRules, Scan, Search, ContextPack, Tools, CLI)

## Offene Punkte
- D1.4 Rest: Symlink-Zyklus-Schutz (aktuell: `Path.walk` folgt Symlinks nicht
  per Default — dokumentiert, kein Handlungsbedarf)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/tools-layer.md|tools-layer]] · [[15-features/system/agent-core.md|Agent Core]]

## Code-Graph (generiert)

- `src/eaccode/repo.py` → [[15-features/system/agent-core.md|Agent Core]]

