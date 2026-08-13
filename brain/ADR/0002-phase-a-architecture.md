---
date: 2026-08-13
status: accepted
phase: A (komplett)
---

# 0002 — Phase-A-Architektur (Router, Loop, Memory, TUI)

## Kontext

Phase A musste ein lauffähiges Fundament liefern: BYOK-Modelle, ein
agentischer Loop, Basis-Tools, Memory und eine Bedienoberfläche — testbar
und wartbar (200–400 LoC/Datei, Cap 600).

## Entscheidungen

- **LiteLLM als einzige LLM-Schnittstelle** (`router.py`): alle Provider über
  `provider/model`-IDs, Keys aus config (env > file), `extra_kwargs` für
  Tool-Calling. `completion_response` (roh) + `completion_text` (Text) getrennt.
- **ReAct-Loop ohne Framework** (`agent.py`): synchron, testbar, Tools als
  Dataclasses mit JSON-Schema; Tool-Fehler töten den Loop nie; Turn-Budget 8.
- **Memory als Markdown-Dateien** (`memory.py`): MEMORY.md/USER.md im
  Datenverzeichnis, Injection in den System-Prompt — kein DB-Zwang (FTS5
  kommt in Phase B für Sessions).
- **Zwei Oberflächen:** REPL (Verhalten, getestet) + Textual-TUI (Worker-Thread
  für Agent-Calls, Slash-Commands, Input-Fokus). REPL bleibt Standard,
  `eaccode tui` für die TUI.
- **Lazy Agent:** wird erst beim ersten Chat gebaut — Management-Kommandos
  (`/config init` …) funktionieren ohne Konfiguration.
- **Permission-Gate:** `run_command` fragt in der REPL interaktiv (y/N),
  Default-Deny; TUI aktuell Deny (C1 bringt das volle System).

## Konsequenzen

- Phase B kann direkt aufbauen: Skills laden Tools/Agent, Session-Store
  persistiert `history`, Subagents nutzen `Agent` isoliert.
- `eaccode -p "<prompt>"` = One-Shot-Modus für Skripte/Cron (Phase C).
- Offen: Modell-Routing nach Task-Typ (D5), Kosten-Metadaten im Katalog.

## Alternativen (verworfen)

- Eigenes Framework/Agent-SDK — zu viel Abstraktion für den Loop-Umfang.
- Chat zuerst im REPL ohne TUI — User-Workflow (CMD → eaccode → testen)
  wollte beide; TUI blieb Skelett (A8).
