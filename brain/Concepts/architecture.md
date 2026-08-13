# Architektur

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

## Tech-Stack (fixiert)

| Bereich | Wahl |
|---|---|
| Sprache | Python 3.12+ |
| Dependencies | uv |
| LLM | LiteLLM (BYOK) |
| TUI | Textual |
| Memory | SQLite + FTS5 + Markdown (MEMORY.md/USER.md) |
| Cron | APScheduler + Daemon |
| Interop | MCP-Protokoll |
| Browser | Playwright |
| Config | YAML + .env (Keys nie im Repo) |
| Packaging | PyInstaller / `uv tool` (Win/Linux/macOS) |
| Qualität | pytest (TDD), ruff, 200–400 LoC/Datei (Cap 600) |

## Phasen

- **A — Foundation & MVP:** Gerüst ✅, Config/Secrets ✅, Router, ReAct-Loop,
  Basis-Tools, Memory, CLI, TUI-Skelett → v0.1.0
- **B — Hermes-Core:** Skills + Learning-Loop, Session-Suche, Memory-Hierarchie,
  Subagents, Parallel-Execution
- **C — Production:** Permissions/Sandbox, Cron+Daemon, MCP, Gateway, Packaging
- **D — Coding-Stärke:** Repo-Index, Diff-Editing, Test-Runner, Git/PR,
  Coding-Routing, Browser

Siehe auch: [[Concepts/vision|Vision]] · [[INDEX|Index]]
