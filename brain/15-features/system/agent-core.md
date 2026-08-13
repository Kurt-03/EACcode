---
name: agent-core
type: system
status: done
phase: A4
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Agent Core (ReAct-Loop)

## Zweck
Der agentische Kern: Modell ↔ Tools im Wechsel, bis eine finale Antwort
kommt — ohne Framework, synchron, testbar.

## Implementierung
- `src/eaccode/agent.py` — `Agent`, `Tool` (Dataclass + JSON-Schema),
  `ToolCall`, `parse_response`, `run(messages, max_turns=8)`
- Tool-Fehler töten den Loop nie (Error-String wird zurückgegeben)
- Turn-Budget → saubere `(stopped: max turns …)`-Meldung
- `last_text()` für die finale Antwort

## Integration
- REPL/TUI nutzen `Agent` mit `BUILTIN_TOOLS` (aus `tools.py`)
- Memory-Injection in den System-Prompt (lazy beim ersten Chat)

## Tests
`tests/test_agent.py` — Loop, Tool-Roundtrip, unbekannte Tools, Exceptions,
Turn-Budget, JSON-Argumente

## Offene Punkte
- Kontext-/Token-Budget-Management (Historie trimmen) — wächst mit B3
- Interrupt während Calls (REPL-Threading) — C1/UX-Thema

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[adr/0002-phase-a-architecture.md|ADR 0002]]

## Code-Graph (generiert)

- `src/eaccode/agent.py` → [[15-features/system/config.md|config.yaml]] · [[15-features/system/permissions.md|permissions]] · [[15-features/system/model-router.md|Model Router]] · [[15-features/system/skill-system.md|skill-system]] · [[15-features/system/tools-layer.md|tools-layer]]

