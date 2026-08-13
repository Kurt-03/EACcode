---
name: repo-understanding
type: system
status: active
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
  max. 2000 Dateien, Tiefe 12), `search()` (Regex, Dateityp-Filter,
  `.gitignore`-Respekt, max. 50 Treffer), `context_pack()` (Modul + Tests
  + Größen), `.gitignore`-Parser (Glob/`**`/Negation `!`)
- Agent-Tools: `repo_scan`, `repo_search`, `repo_context` — read-only
  (laufen frei im ask-Modus)

## Verifiziert
- (wird beim Live-Test ergänzt)

## Tests
`tests/test_repo.py`

## Offene Punkte
- D1.4: Zyklus-Erkennung (Symlinks) + Grenz-Tests

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/tools-layer.md|Tools-Layer]] · [[15-features/system/agent-core.md|Agent Core]]
