---
name: session-store
type: system
status: done
phase: B3
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Session-Store (B3)

## Zweck
Gespräche persistieren und durchsuchen: SQLite + FTS5-Volltextsuche über
alle alten Sessions (Discovery/Scroll/Browse) — die Basis dafür, dass
eaccode sich an frühere Sessions erinnern kann.

## Implementierung
- `src/eaccode/store.py` — SQLite (`data/sessions.db`): Tabellen `sessions`
  + `messages` + FTS5-Index (mit LIKE-Fallback), `new_session`,
  `add_message`, `browse`, `search`, `show`
- REPL speichert jede Chat-Runde (User + Assistant) mit Session-Titel
- Kommandos: `/session browse|search|show` → [[15-features/commands/session.md|session]]
- Agent-Tool: `session_search` (Agent kann alte Gespräche durchsuchen)

## Verifiziert (live, 2026-08-13)
- Chat-Runde gespeichert, Titel automatisch gesetzt
- `/session search LiteLLM` fand die Session mit Snippet

## Tests
`tests/test_store.py` (11) + TestSessionCommands + REPL-Persistenz-Tests

## Offene Punkte (Hermes-Vergleich 2026-08-13)
- ✅ Scroll-Modus nachgerüstet (anchored window oder letzte N; `session_scroll`-Tool)
- ✅ **@session:-Links nachgerüstet**: REPL löst `@session:<id>` zu
  Kontext-Nachrichten für den Agenten auf (2026-08-13)
- Profil-Scoping (Hermes: pro Profil getrennte Stores)
- Dedup nach Session-Linie bei Discovery-Treffern

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/memory.md|Memory]]

## Code-Graph (generiert)

- `src/eaccode/store.py` → [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/config.md|Config]]

