# eaccode Brain — Index

Das Wissensgedächtnis für die Entwicklung von **eaccode** — dem selbstverbessernden
Generalist-Agenten (Hermes × Claude Code Hybrid, BYOK, lokal, cross-platform).

> **Regel:** Dieses Brain speichert *Wissen & Entscheidungen*.
> Pläne, Tasks und Status gehören ins Repo (`C:\Projekte\EACcode V3`) bzw. in
> `.hermes/plans/` — hier wird nur verlinkt, nicht dupliziert.

## Bereiche

| Bereich | Inhalt |
|---|---|
| [[ADR/0001-config-yaml-design\|ADR]] | Architektur-Entscheidungen mit Begründung (`YYYY-NNNN-titel.md`) |
| [[Concepts/vision\|Concepts]] | Vision, Architektur, Phasen-Konzepte |
| [[Research/README\|Research]] | Provider- und Tool-Vergleiche, Evaluierungen |
| [[Backlog/offene-fragen\|Backlog]] | Offene Entscheidungen, Ideen, Fragen |

## Aktuelle Entscheidungen

- **2026-08-13** — [[ADR/0001-config-yaml-design|config.yaml + Secrets-Design]] (Phase A2)
- **2026-08-13** — Version dauerhaft `0.0.1`; interaktive REPL zuerst (Chat kommt in A7)
- **2026-08-13** — [[ADR/0002-phase-a-architecture|Phase-A-Architektur]] (Router, Loop, Memory, TUI)

## Projekt-Stand (Kurzreferenz)

- **Phase A (Foundation & MVP) KOMPLETT ✅** (2026-08-13): A1–A8 umgesetzt, 150 Tests grün
- Stand: v0.0.1 — eaccode chatfähig (REPL + TUI), BYOK-Router, Memory, Tools
- **Als Nächstes: Phase B (Hermes-Core)** — Skills + Learning-Loop, Session-Suche, Subagents
- Master-Plan: `.hermes/plans/2026-08-13_130000-eaccode-v2-master-plan.md`
- Verifikations-Fahrplan: `docs/manual-test.md` im Repo
- Repo: `C:\Projekte\EACcode V3` · Tests: `uv run pytest` · Live: `eaccode` in der CMD

## Links

- [[Concepts/vision|Vision]] · [[Concepts/architecture|Architektur]] · [[Backlog/offene-fragen|Offene Fragen]]
