---
date: 2026-08-13
status: active
area: architecture
tags: [area/architecture, type/area]
---

# Architektur *(timeless — wie das System gebaut ist)*

```
┌──────────────────────────────────────────────────────────────┐
│  Surfaces: CLI / TUI / (später: Gateway Telegram, Discord…) │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  Agent Core — ReAct / Plan-Act-Observe Loop                  │
│  · Tool-Calling · Subagents · Parallel-Execution             │
└───────────┬──────────────────────────────┬───────────────────┘
            │                              │
┌───────────▼─────────────┐   ┌────────────▼───────────────────┐
│  Memory & Learning      │   │  Model Router (BYOK)           │
│  · MEMORY.md / USER.md  │   │  · LiteLLM (alle Provider)     │
│  · Session-Store (FTS5) │   │  · Fallback-Chain              │
│  · Skills + Learning    │   │  · Routing nach Task-Typ       │
└─────────────────────────┘   └────────────────────────────────┘
            │
┌───────────▼──────────────────────────────────────────────────┐
│  Tools Layer: Files · Terminal · Web · Git · Browser ·       │
│  Test-Runner · Diff-Editing · MCP · Skills                   │
└──────────────────────────────────────────────────────────────┘
```

## Kern-Entscheidungen (Details in den ADRs)

- **LiteLLM als einzige LLM-Schnittstelle** — `router.py`: alle Provider über
  `provider/model`-IDs; Keys aus config (env > file); `completion_response`
  (roh) + `completion_text` (Text) getrennt → [[ADR/0002-phase-a-architecture.md|0002-phase-a-architecture]]
- **ReAct-Loop ohne Framework** — `agent.py`: synchron, testbar, Tools als
  Dataclasses mit JSON-Schema; Tool-Fehler töten den Loop nie
- **Memory als Markdown** — MEMORY.md/USER.md + System-Prompt-Injection;
  Session-Suche (FTS5) gebaut in Phase B (B3)
- **Zwei Oberflächen** — REPL (Verhalten, getestet) + Textual-TUI (Worker);
  `eaccode tui` startet die TUI
- **Lazy Agent** — wird erst beim ersten Chat gebaut (Management-Kommandos
  funktionieren ohne Konfiguration)
- **Permission-Gate** — `run_command` fragt in der REPL y/N, Default-Deny

## Phasen-Zielbild

- **A — Foundation & MVP ✅** → REPL+TUI, BYOK, Memory, Tools
- **B — Hermes-Core** → Skills + Learning-Loop, Session-Suche, Subagents
- **C — Production** → Permissions/Sandbox, Cron+Daemon, MCP, Gateway, Packaging
- **D — Coding-Stärke** → Repo-Index, Diff-Editing, Test-Runner, Git/PR, Routing, Browser
