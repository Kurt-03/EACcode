---
name: cmd-tui
type: command
status: done
phase: A8
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Start: eaccode tui

## Zweck
Startet die Textual-TUI (Chat-Log, Input unten, Slash-Commands, Worker).

## Syntax
```
eaccode tui
```
Beenden: `Ctrl+Q` (Binding in der App).

## Implementierung
- `src/eaccode/cli.py` — `first == "tui"` → `EaccodeApp(agent_factory=build_agent).run()`
- `src/eaccode/tui.py` — App, `@work(thread=True)` für Agent-Calls

## Tests
`tests/test_tui.py` — Fokus, Slash, Clear, Chat-Roundtrip (Pilot)

## Offene Punkte
- Hermes-Style: Glyphen ❯/⚡/·/◈, StatusRule, Fuzzy-Slash-Overlay, `/copy`

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/tui.md|TUI]]
