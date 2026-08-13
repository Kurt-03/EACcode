---
name: parallel-execution
type: system
status: done
phase: B6
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Parallel-Execution (B6)

## Zweck
Mehrere Tool-Calls eines Turns laufen gleichzeitig (Subagents, http_get,
Recherchen) — mit stabiler Zusammenführung und Fehler-Isolation.

## Implementierung
- `src/eaccode/agent.py` — `run()`: Tool-Calls eines Turns über
  `ThreadPoolExecutor` (max. 6 Worker), Reihenfolge stabil via `pool.map`
- Fehler-Isolation: `_execute_tool` fängt jede Exception → Error-String;
  ein kaputtes Tool blockiert die anderen nicht
- `cancel_event` wird zwischen Turns geprüft (Timeout-Guard)
- Subagent-Limit zusätzlich durch `SubagentPool` (max. 6 parallel)

## Verifiziert (live, 2026-08-13)
- 2 `http_get`-Subagents parallel (17 s gesamt), Reihenfolge korrekt

## Tests
`tests/test_agent.py` — TestParallelTools (Zeit < sequenziell, 2 Ergebnisse)
+ Fehler-Isolation bei parallelen Calls (2026-08-13 ergänzt)

## Offene Punkte
- Laufende Tool-Calls können erst NACH dem Turn abgebrochen werden
  (cancel wirkt zwischen Turns)
- Permission-Race bei parallelen `run_command`-Prompts (C1)
- Subagent-Ergebnisse in Session-Store loggen (B3-Erweiterung)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/subagents.md|subagents]]
