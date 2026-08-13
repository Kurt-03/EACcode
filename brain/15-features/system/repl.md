---
name: repl
type: system
status: done
phase: A7
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: REPL (Chat + Slash-Commands)

## Zweck
Die Standard-Oberfläche: `eaccode` in der CMD starten → Banner → Slash-
Commands für Verwaltung, normaler Text geht an den Agent (Konversation mit
History).

## Implementierung
- `src/eaccode/repl.py` — `run_repl(stdin, stdout, agent, agent_factory)`
- **Lazy Agent:** wird erst beim ersten Chat gebaut (Management-Kommandos
  funktionieren ohne Konfiguration)
- Konversations-History im Chat; `/clear` resetet sie
- Interaktiver Permission-Prompt (`Allow: <cmd> [y/N]`) verdrahtet
  `tools.permission_handler`
- Ctrl+C / EOF → sauberes `bye`, Exit 0

## Kommandos
`/help /version /clear /config /provider /model /memory /exit`

## Tests
`tests/test_repl.py` — Slash, Chat-Roundtrip, History, Fehler-Isolation,
Memory in REPL

## Offene Punkte
- (keine für A)

## Verknüpft
[[../README|Feature-Register]] · [[../..//tui|TUI]] · [[one-shot|One-Shot]]
