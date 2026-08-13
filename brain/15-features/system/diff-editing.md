---
name: diff-editing
type: system
status: done
phase: D2
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Diff-Editing (D2)

## Zweck
Präzises Editieren statt Rewrites: fuzzy Patches, Multi-File-Edits mit
Batch-Rollback, Undo-Stack, Syntax-Schutz.

## Implementierung
- `src/eaccode/editing.py` — `apply_patch` (exakt oder fuzzy: Zeichen-Level
  Fenster-Scan + zeilenbasierte Substitution mit Verifikation),
  `apply_multiple` (atomar: ein Fehler → ganze Batch zurück),
  `EditSession` (Backup-Stack in `data/edits/`, max. 20)
- Syntax-Check via `py_compile` VOR dem Schreiben (.py)
- Tools: `patch_file`, `patch_multiple`, `undo_edit` — mutierend (ask)

## Verifiziert (live, 2026-08-13 — Übungs-Repo `C:\Projekte\eaccode-praxis`)
- Agent fixte `add`-Bug (a-b → a+b) per patch_file; run_tests grün
- `multiply` + Test ergänzt (2 Dateien), 3 Tests grün, Commit gesetzt

## Tests
`tests/test_editing.py` (15: exakt, fuzzy, mehrdeutig, Syntax, Rollback, Multi)

## Offene Punkte
- Ruff-Integration in den Syntax-Check (D2.4: py_compile reicht aktuell)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/repo-understanding.md|repo-understanding]] · [[15-features/system/tools-layer.md|tools-layer]]

## Code-Graph (generiert)

- `src/eaccode/editing.py` → [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/config.md|config.yaml]]

