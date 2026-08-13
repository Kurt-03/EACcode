---
date: 2026-08-13
status: archived
area: projects
tags: [type/snapshot, project/phase-a]
---

# Phase A — Abschluss-Snapshot *(dated)*

**2026-08-13: Phase A (Foundation & MVP) komplett abgeschlossen.**

## Was gebaut wurde (A1–A8)

| Step | Inhalt | Commit |
|---|---|---|
| A1 | Projektgerüst (uv, CI Win/Linux/macOS, CLI) | `df4bbe1` |
| A2 | Config & Secrets (maskiert, chmod 600, .env) | `44c2c28` |
| A3 | BYOK Model Router (LiteLLM, Provider, Katalog, Fallback) | `9531bc9` |
| A4 | Agent Core (ReAct-Loop mit Tool-Calling) | `d78b6d7` |
| A5 | Basis-Tools (Files, Terminal+Permission, Web, Info) | `c2a4494` |
| A6+A7 | Memory (MEMORY.md/USER.md) · Chat-REPL · `-p` | `dfdf7d2` |
| A8 | TUI (Textual, Input-Fokus, Slash-Commands, Worker) | `2b73c96` |

## Verifiziert (live)

- Session: `/version` · `/config show` · `/provider list` · `/model list` ·
  `/memory add` — alles funktional
- `eaccode -p "…"` One-Shot, sauberer Fehlerpfad ohne Key
- `eaccode tui` rendert, Input-Fokus gesetzt
- 150 Tests grün, ruff clean (Stand 2026-08-13)
- **2026-08-13: User-Live-Test komplett durchgelaufen** — „geht alles";
  MiniMax als erster Provider mit Key + Live-Ping (`minimax/MiniMax-M3` → pong),
  Chat-Calls mit Antwort; Default auf MiniMax-M3 gesetzt

## Lessons

- Anzeige-Filter im Hermes-Desktop-Terminal maskiert gelegentlich `not`/`None`
  → echte Werte per Datei-Umleitung prüfen
- Altlasten des Vorgänger-Projekts (PyInstaller-exes, Daten) im
  `%LOCALAPPDATA%\eaccode`-Ordner entfernt — Backup: `%LOCALAPPDATA%\eaccode-old`
- uv-tool-Launcher-Prozesse vor Reinstall killen (Datei-Sperre auf Windows)

## Nächste Schritte

→ [[10-projects/phase-b.md|Phase B]] (Skills, Learning-Loop, Session-Suche, Subagents)
