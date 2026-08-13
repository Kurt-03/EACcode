---
name: subagents
type: system
status: done
phase: B5
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Subagents (B5)

## Zweck
Der Haupt-Agent kann fokussierte Helfer spawnen: isolierter Kontext, nur
ausgewählte Tools, nur die finale Antwort kommt zurück. Max. 6 parallel,
Warteschlange für den Rest.

## Implementierung
- `src/eaccode/subagents.py` — `SubagentPool` (Semaphore-Limit), Timeout-
  Schutz (daemon-Thread + join), `spawn_subagent`-Agent-Tool
- Subagent = eigene `Agent`-Instanz: `use_skills=False`, kein Nudge,
  max. 6 Turns, nur die angeforderten Tools (unbekannte → Fehler)
- **Agent-Loop:** mehrere Tool-Calls eines Turns laufen parallel
  (ThreadPoolExecutor) — dadurch laufen 2 `spawn_subagent`-Calls echt parallel

## Verifiziert (live, 2026-08-13 — DoD erfüllt)
- 2 Subagents parallel gespawnt (nur `http_get`), example.com → Titel,
  example.org → 403 sauber gemeldet; beide liefen gleichzeitig (17 s gesamt)
- Reasoning-only-Subagent (tools=[]) lieferte Gedicht ohne Tools

## Tests
`tests/test_subagents.py` (8: Pool, Kontext, Fehler, Timeout+Cancel, Limit,
Tool-Auswahl, Reasoning-only) + Parallel-Loop- & Cancel-Tests in `test_agent.py`

## Offene Punkte
- ✅ Timeout-Guard ✅ (cancel_event)
- ✅ Worker-Cap ✅ (6 pro Turn)
- ✅ Subagent-/Tool-Ergebnisse in Session-Store ✅ (2026-08-13: volle
  Runden-Persistenz inkl. tool-Messages)
- ✅ Permission-Race bei parallelen Prompts ✅ (ask_handler serialisiert)
- Nächste Stufe: Task-Delegation mit Ergebnis-Schema (D-Phase)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/session-store.md|session-store]] · [[15-features/agents/README.md|README]]

## Code-Graph (generiert)

- `src/eaccode/subagents.py` → [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/config.md|config.yaml]]

