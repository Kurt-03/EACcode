---
name: subagents
type: system
status: active
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

## Verifiziert (live, 2026-08-13)
- (wird beim Live-Test ergänzt)

## Tests
`tests/test_subagents.py` + Parallel-Loop-Test in `tests/test_agent.py`

## Offene Punkte
- Timeout-Abbruch hängender Subagents (Thread läuft als daemon weiter)
- Subagent-Ergebnisse in Session-Store loggen
- Permission-Race bei parallelen `run_command`-Prompts (C1)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/session-store.md|Session-Store]]
