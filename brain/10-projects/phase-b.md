---
date: 2026-08-13
status: active
area: projects
tags: [project, phase-b]
---

# Phase B — Hermes-Core (Skizze)

Ziel: Das Lern- und Gedächtnis-Herz — der Unterschied zu „normalen" Agents.

## Schritte

1. **B1 Skill-System ✅** — SKILL.md (Frontmatter: name/description/trigger),
   Skill-Verzeichnisse, Laden per Trigger, Skill-View, Skill-Skripte/Templates
2. **B2 Learning-Loop ✅** — Post-Task-Review (wann ein Skill entsteht),
   Skill-Erstellung als Tool-Aktion, Skill-Verbesserung (patch), Dedup/Pruning
3. **B3 Session-Store ✅** — SQLite + FTS5, `session_search`
   (Discovery/Scroll/Browse), Session-Links
4. **B4 Memory-Hierarchie ✅** — global vs. projektbezogen, Char-Budget,
   Batch-Kuration, Konflikte
5. **B5 Subagents ✅** — isolierte Kontexte, eigene Tool-Sets, Limits
6. **B6 Parallel-Execution ✅** — mehrere Tool-Calls gleichzeitig, Fehler-Isolation

## Phase B — KOMPLETT ✅ (2026-08-13)

DoD erfüllt: Agent hat selbst einen Skill erstellt + verbessert (B1/B2),
Session-Suche findet alte Gespräche (B3), Memory kuratiert der Agent selbst
(B4), 2 Subagents parallel (B5/B6). Restpunkte (bewusst notiert):
Subagent-Ergebnisse in Session-Store loggen, Permission-Race (C1),
Timeout-Abbruch laufender Tool-Calls (nach Turn-Grenze).
→ Abschluss-Snapshot: [[50-archive/phase-b.md|phase-b]]

## DoD

- Der Agent hat nach einem komplexen Task **selbst einen Skill erstellt**
  und beim zweiten Mal verbessert
- Session-Suche findet alte Gespräche
- 2 Subagents parallel

## Querverweise

- Master-Plan: `.hermes/plans/2026-08-13_130000-eaccode-v2-master-plan.md`
- Architektur: [[20-areas/architecture.md|Architektur]]
