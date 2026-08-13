---
name: test-runner
type: system
status: done
phase: D3
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Test-Runner (D3)

## Zweck
Der Agent führt Test-Suiten aus und versteht die Ergebnisse: strukturierter
Report (Pass/Fail-Zähler, fehlgeschlagene Tests), Test→Fix→Loop als
Agent-Verhalten (rot → fix → grün).

## Implementierung
- `src/eaccode/testrunner.py` — `run_tests` (pytest mit Fallback-Kette:
  Tool-Interpreter → `uv run pytest` → PATH `pytest`), `parse_failures`
  (FAILED/ERROR-Zeilen), `format_report` (kompakter Status + Fehlerliste)
- Tool: `run_tests` — read-only (frei im ask-Modus)
- Policy im Tool-Text: nie fertig melden/committen bei roten Tests

## Verifiziert (live, 2026-08-13 — Übungs-Repo)
- rote Suite → Fehler-Parsing; nach Fix → grün; Fallback-Kette griff
  (Tool-venv ohne pytest → `uv run pytest`)

## Tests
`tests/test_testrunner.py` (8: grün/rot, Parsing, Fallback, Tool)

## Offene Punkte
- Coverage (D3.4): `--cov`-Flag vorhanden, pytest-cov optional

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/diff-editing.md|diff-editing]] · [[15-features/system/git-pr.md|git-pr]]

## Code-Graph (generiert)

- `src/eaccode/testrunner.py` → [[15-features/system/agent-core.md|Agent Core]]

