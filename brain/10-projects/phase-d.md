---
date: 2026-08-13
status: active
area: projects
tags: [type/plan, project/phase-d]
---

# Phase D — Coding-Stärke (Plan)

**Ziel (Master-Plan):** Claude-Code-Level beim Coden — Repo-Verständnis,
Diff-Editing, Test-Loop, Git/PR, Coding-Routing, Browser.
**DoD:** eaccode nimmt ein Issue aus einem fremden Repo (Live-Ziel:
`C:\Projekte\_ref\hermes`), implementiert es multi-file mit Tests, lässt die
Suite laufen und öffnet einen PR — mit Routing (teures Modell nur fürs
Coden, günstiges für Recherche).
**Status:** C1–C3 fertig; C4 (Telegram) + C5 (Packaging) vom Nutzer
bewusst **viel später** → D wird jetzt aktiv.

---

## D0 — Basis-Aufräumen (Voraussetzung, ~1 h)

- **D0.1 Slash-Commands**: Quote-Parsing (mehrwortige Argumente, z. B.
  `/skill new --description "mehrere Worte"`), `/job` + `/mcp` auch im REPL,
  konsistenter Arg-Parser + Tests (behebt den Nutzer-Merkpunkt)
- **D0.2 Memory-Härtung**: Cross-Process-File-Lock + Drift-Guard
  (Hermes-Parität B4, schließt die letzte Memory-Lücke)

## D1 — Repo-Verständnis (4 Tasks)

| Task | Inhalt | Verifikation |
|---|---|---|
| D1.1 | `repo_scan`-Tool: Struktur-Index (Ordner/Dateien, `.gitignore`-Respekt, Größen) | Hermes-Repo scannen |
| D1.2 | `repo_search`: rekursive Suche mit Pfad-relative-Ausgabe + Dateityp-Filter | gezielte Suche |
| D1.3 | Context-Packs: verwandte Dateien bündeln (z. B. Modul + Tests) | Bundle laden |
| D1.4 | Zyklus-Erkennung + Grenzen (max. Dateien pro Scan) | große Repos |

## D2 — Diff-Editing (5 Tasks)

| Task | Inhalt | Verifikation |
|---|---|---|
| D2.1 | `patch_file`-Tool (fuzzy old/new) + Syntax-Check nach Edit | Patch + `py_compile` |
| D2.2 | Multi-File-Edits (ein Aufruf, mehrere Dateien) | 2 Dateien patchen |
| D2.3 | Rollback: Undo-Stapel pro Session (Backups vor Edit) | Edit → Rollback → Original |
| D2.4 | Syntax-Check-Integration (ruff wenn verfügbar) | kaputten Patch abfangen |
| D2.5 | Fehler-Meldung mit Zeilenkontext (diff-artig) | Fehlerszenario |

## D3 — Test-Runner (4 Tasks)

| Task | Inhalt | Verifikation |
|---|---|---|
| D3.1 | `run_tests`-Tool (pytest, Exit-Code, stdout) | echte Suite |
| D3.2 | Fehler-Parsing (FAILED-Zeilen + Traceback-Snippets strukturiert) | rote Suite |
| D3.3 | Test→Fix→Test-Loop (rot → fix → grün, Abbruch nach N Versuchen) | echte RED-GREEN |
| D3.4 | Coverage-Auswertung (pytest-cov wenn verfügbar) | Coverage-Bericht |

## D4 — Git/PR (4 Tasks)

| Task | Inhalt | Verifikation |
|---|---|---|
| D4.1 | Git-Read-Tools (status/diff/log/branch, safe) | Hermes-Repo |
| D4.2 | Commit-Workflow (Policy: nie bei roten Tests, klare Messages) | Feature-Commit |
| D4.3 | Branch/PR-Workflow via gh-CLI (falls verfügbar) | Feature-Branch + Dry-Run |
| D4.4 | Abbruch + Revert-Pfade | Rollback-Szenario |

## D5 — ~~Coding-Routing~~ *(entfernt 2026-08-13, Nutzer)*

→ **Optionale Idee (nur auf Nachfrage):** Task-Klassifikation (code/test/
refactor/recherche/routine) + Modell je Task-Typ (stark für Code, günstig
für Routine) + Fallback-Kette. Nicht Teil der Roadmap.

## D6 — Browser (3 Tasks)

| Task | Inhalt | Verifikation |
|---|---|---|
| D6.1 | Playwright: Navigate/Click/Extract (optional dependency) | eigene Seite |
| D6.2 | Screenshots + Session-Persistenz | Screenshot + Wiederkehr |
| D6.3 | Fehler-Isolation + Timeout | kaputte Seite |

---

## Reihenfolge & Regeln
D0 → D1 → D2 → D3 → D4 → D6; ein Feature einzeln bauen und
verifizieren (TDD, 4-Stufen-Regel, Brain-Notiz + Test-Map pro Schritt).
Browser (D6) ist der größte Brocken — wird am Ende gemacht, der DoD
braucht ihn nicht. D5 (Routing) wurde vom Nutzer entfernt → optionale Idee.

## Verknüpft
[[10-projects/README.md|Dashboard]] · [[15-features/README.md|Feature-Register]] · [[50-archive/phase-b.md|phase-b]] · [[15-features/system/agent-core.md|Agent Core]]
