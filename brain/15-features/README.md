# Feature-Register

**Jedes Feature von eaccode hat hier eine eigene Notiz** mit Status — separat
getrackt. Neues Feature → Notiz anlegen (`_templates/feature.md`) + Zeile hier
eintragen.

## Status-Legende

`planned` → `active` → `done` · `blocked` (wartet auf anderes)

## Register

| Feature | Typ | Status | Phase | Notiz |
|---|---|---|---|---|
| config.yaml | system | done | A2 | [[15-features/system/config.md|config.yaml]] |
| Secret-Handling | system | done | A2 | [[15-features/system/secrets.md|Secrets]] |
| Model Router (BYOK) | system | done | A3 | [[15-features/system/model-router.md|Model Router]] |
| Provider: OpenRouter | provider | done | A3 | [[15-features/providers/openrouter.md|OpenRouter]] |
| Provider: Ollama | provider | done | A3 | [[15-features/providers/ollama.md|Ollama]] |
| Provider: MiniMax | provider | done | A3 | [[15-features/providers/minimax.md|minimax]] |
| Agent Core (ReAct) | system | done | A4 | [[15-features/system/agent-core.md|Agent Core]] |
| Tool: read_file | tool | done | A5 | [[15-features/tools/read-file.md|Tool: read_file]] |
| Tool: write_file | tool | done | A5 | [[15-features/tools/write-file.md|Tool: write_file]] |
| Tool: list_files | tool | done | A5 | [[15-features/tools/list-files.md|Tool: list_files]] |
| Tool: search_files | tool | done | A5 | [[15-features/tools/search-files.md|Tool: search_files]] |
| Tool: run_command | tool | done | A5 | [[15-features/tools/run-command.md|Tool: run_command]] |
| Tool: http_get | tool | done | A5 | [[15-features/tools/http-get.md|Tool: http_get]] |
| Tool: web_search | tool | done | A5 | [[15-features/tools/web-search.md|Tool: web_search]] |
| Tool: current_time | tool | done | A5 | [[15-features/tools/current-time.md|Tool: current_time]] |
| Tool: system_info | tool | done | A5 | [[15-features/tools/system-info.md|Tool: system_info]] |
| Memory (MEMORY.md/USER.md) | system | done | A6/B4 | [[15-features/system/memory.md\|Memory]] |
| REPL (Chat + Slash) | system | done | A7 | [[15-features/system/repl.md|REPL]] |
| One-Shot `-p` | system | done | A7 | [[15-features/system/one-shot.md|One-Shot]] |
| TUI (Textual) | system | done | A8 | [[15-features/system/tui.md|TUI]] |
| Permission-Gate | system | done (REPL) | A5/C1 | [[15-features/system/permission-gate.md|Permission-Gate]] |
| Subagents | agent | done | B5 | [[15-features/system/subagents.md\|subagents]] |
| Parallel-Execution | system | done | B6 | [[15-features/system/parallel-execution.md\|parallel-execution]] |
| Permissions (C1) | system | done | C1 | [[15-features/system/permissions.md\|permissions]] |
| Repo-Verständnis (D1) | system | done | D1 | [[15-features/system/repo-understanding.md\|repo-understanding]] |
| Diff-Editing (D2) | system | done | D2 | [[15-features/system/diff-editing.md\|diff-editing]] |
| Test-Runner (D3) | system | done | D3 | [[15-features/system/test-runner.md\|test-runner]] |
| Git & PR (D4) | system | done | D4 | [[15-features/system/git-pr.md\|git-pr]] |
| Browser (D6) | system | done | D6 | [[15-features/system/browser.md\|browser]] |
| Cron & Daemon (C2) | system | done | C2 | [[15-features/system/cron-daemon.md\|cron-daemon]] |
| MCP-Client (C3) | system | done | C3 | [[15-features/system/mcp-client.md\|mcp-client]] |
| Skill-System | system | done | B1 | [[15-features/system/skill-system.md\|skill-system]] |
| Learning-Loop | system | done | B2 | [[15-features/system/learning-loop.md\|learning-loop]] |
| Session-Store (FTS5) | system | done | B3 | [[15-features/system/session-store.md\|session-store]] |
| Memory-Hierarchie | system | done | B4 | [[15-features/system/memory.md\|Memory]] |
| Commands (alle `/`) | system | done | A–B | [[15-features/commands/README.md\|README]] |

*Stand: 2026-08-13 — Phase A ✅ · B ✅ · C1–C3 ✅ · D ✅ KOMPLETT (402 Tests); C4/C5 auf später verschoben*
