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
| Subagents | agent | active | B5 | [[15-features/system/subagents.md\|Subagents]] |
| Skill-System | system | done | B1 | [[15-features/system/skill-system.md\|skill-system]] |
| Learning-Loop | system | done | B2 | [[15-features/system/learning-loop.md\|learning-loop]] |
| Session-Store (FTS5) | system | done | B3 | [[15-features/system/session-store.md\|Session-Store]] |
| Memory-Hierarchie | system | done | B4 | [[15-features/system/memory.md\|Memory]] |
| Commands (alle `/`) | system | done | A–B | [[15-features/commands/README.md\|Commands-Index]] |

*Stand: 2026-08-13 — Phase A komplett; Phase B: B1/B2 fertig, B3–B6 offen*
