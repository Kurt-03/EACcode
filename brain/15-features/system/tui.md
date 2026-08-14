---
name: tui
type: system
status: done
phase: A8
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: TUI (Textual)

## Zweck
Reiche Chat-Oberfläche: Log-Pane, Input unten (Fokus beim Start), Slash-
Commands, Agent-Calls im Worker-Thread (UI blockiert nie).

## Implementierung
- `src/eaccode/tui.py` — `EaccodeApp` (Textual)
- `@work(thread=True)` + `AgentResult`-Message → UI-Thread-Update
- Rollen-Marker: `>` (user) / `eaccode:` (agent)
- Start: `eaccode tui` · Beenden: `Ctrl+Q`
- Permission: aktuell Deny (kein Prompt im Skelett)

## Tests
`tests/test_tui.py` — Fokus, Slash im Log, Clear, Chat-Roundtrip (Pilot)

## Offene Punkte
- Hermes-Style: Rollen-Glyphen ❯/⚡/·/◈, StatusRule, Fuzzy-Slash-Overlay
- `/copy` bei Maus-Selektion, Scrollback-Erhalt
- Interaktiver Permission-Prompt (C1)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/repl.md|REPL]]

## Code-Graph (generiert)

- `src/eaccode/tui.py` → [[15-features/system/agent-core.md|Agent Core]] · [[15-features/commands/README.md|README]] · [[15-features/system/memory.md|Memory]] · [[15-features/system/repl.md|REPL]]

