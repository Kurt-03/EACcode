# Feature-Register

**Jedes Feature von eaccode hat hier eine eigene Notiz** mit Status — separat
getrackt. Neues Feature → Notiz anlegen (`_templates/feature.md`) + Zeile hier
eintragen.

## Status-Legende

`planned` → `active` → `done` · `blocked` (wartet auf anderes)

## Provider

| Feature | Status | Phase | Notiz |
|---|---|---|---|
| Provider: Anthropic (SDK direkt) | done | 08-17 | [[15-features/providers/anthropic.md\|anthropic]] |
| Provider: OpenRouter (legacy — OpenAI-compat-Adapter fehlt) | done (legacy) | A3 | [[15-features/providers/openrouter.md\|OpenRouter]] |
| Provider: Ollama (legacy — OpenAI-compat-Adapter fehlt) | done (legacy) | A3 | [[15-features/providers/ollama.md\|Ollama]] |
| Provider: MiniMax (via Anthropic-Adapter) | done | A3 | [[15-features/providers/minimax.md\|minimax]] |
| Provider: Base Types (StreamChunk, Provider Protocol) | done | 08-17 | [[15-features/providers/base.md\|base]] |
| Provider: Registry (Detection + Cache) | done | 08-17 | [[15-features/providers/registry.md\|registry]] |

## Tools

| Feature | Status | Phase | Notiz |
|---|---|---|---|
| Tool: read_file | done | A5 | [[15-features/tools/read-file.md\|Tool: read_file]] |
| Tool: write_file | done | A5 | [[15-features/tools/write-file.md\|Tool: write_file]] |
| Tool: list_files | done | A5 | [[15-features/tools/list-files.md\|Tool: list_files]] |
| Tool: search_files | done | A5 | [[15-features/tools/search-files.md\|Tool: search_files]] |
| Tool: run_command | **entfernt 08-18** (Commit `11faf9c`) | A5 | *Plan H: keine eigene Note mehr* |
| Tool: http_get | done | A5 | [[15-features/tools/http-get.md\|Tool: http_get]] |
| Tool: web_search | done | A5 | [[15-features/tools/web-search.md\|Tool: web_search]] |
| Tool: current_time | done | A5 | [[15-features/tools/current-time.md\|Tool: current_time]] |
| Tool: system_info | done | A5 | [[15-features/tools/system-info.md\|Tool: system_info]] |

## System — Core / Loop / Loop-Components

| Feature | Status | Phase | Notiz |
|---|---|---|---|
| config.yaml | done | A2 | [[15-features/system/config.md\|config.yaml]] |
| Secrets-Handling | done | A2 | [[15-features/system/secrets.md\|Secrets]] |
| Model Router (BYOK) | done | A3 | [[15-features/system/model-router.md\|Model Router]] |
| Models.dev Catalog | done | 08-17 | [[15-features/system/models-dev.md\|models-dev]] |
| Provider-Architektur | done | 08-17 | [[15-features/system/providers.md\|providers]] |
| Agent Core (ReAct-Loop) | done | A4 | [[15-features/system/agent-core.md\|Agent Core]] |
| Tools Layer | done | A5 | [[15-features/system/tools-layer.md\|tools-layer]] |
| Memory (MEMORY.md/USER.md) | done | A6/B4 | [[15-features/system/memory.md\|Memory]] |
| REPL (Chat + Slash) | done | A7 | [[15-features/system/repl.md\|REPL]] |
| One-Shot `-p` | done | A7 | [[15-features/system/one-shot.md\|One-Shot]] |
| TUI (Textual) | done | A8 | [[15-features/system/tui.md\|TUI]] |
| Subagents | done | B5 | [[15-features/system/subagents.md\|subagents]] |
| Parallel-Execution | done | B6 | [[15-features/system/parallel-execution.md\|parallel-execution]] |
| Slash-Palette | done | D0.1+ | [[15-features/system/slash-palette.md\|slash-palette]] |
| Start-Banner | done | D0.1 | [[15-features/system/start-banner.md\|start-banner]] |
| Repo-Verständnis (D1) | done | D1 | [[15-features/system/repo-understanding.md\|repo-understanding]] |
| Diff-Editing (D2) | done | D2 | [[15-features/system/diff-editing.md\|diff-editing]] |
| Test-Runner (D3) | done | D3 | [[15-features/system/test-runner.md\|test-runner]] |
| Git & PR (D4) | done | D4 | [[15-features/system/git-pr.md\|git-pr]] |
| Browser (D6) | done | D6 | [[15-features/system/browser.md\|browser]] |
| Cron & Daemon (C2) | done | C2 | [[15-features/system/cron-daemon.md\|cron-daemon]] |
| MCP-Client (C3) | done | C3 | [[15-features/system/mcp-client.md\|mcp-client]] |
| Skill-System | done | B1 | [[15-features/system/skill-system.md\|skill-system]] |
| Learning-Loop | done | B2 | [[15-features/system/learning-loop.md\|learning-loop]] |
| Session-Store (FTS5) | done | B3 | [[15-features/system/session-store.md\|session-store]] |
| Commands (alle `/`) | done | A–B | [[15-features/commands/README.md\|README]] |

## System — Permissions + Safety

| Feature | Status | Phase | Notiz |
|---|---|---|---|
| Permission-Gate (Legacy, ersetzt durch Smart Mode) | done (REPL) | A5/C1 | [[15-features/system/permission-gate.md\|Permission-Gate]] |
| Permissions (Smart Mode, 5 Outcomes) | done | C1+08-18 | [[15-features/system/permissions.md\|permissions]] · [[ADR/0003-smart-approval-mode.md\|0003-smart-approval-mode]] |
| Smart Approval (Aux LLM + XML-Delimiters) | done | 08-18 | [[15-features/system/smart-approval.md\|smart-approval]] |
| Streaming-Buffer-Fix | done | 08-18 | [[15-features/system/streaming-buffer-fix.md\|streaming-buffer-fix]] |
| /approvals (Smart Switch + Allow-Path) | done | 08-18 | [[15-features/commands/approvals.md\|approvals]] |
| Persistent Block-List (deny_always) | done | 08-18 C.8 | [[15-features/system/blocked-list.md\|blocked-list]] |
| Human-Wait-Window (ContextVar) | done | 08-18 C.3 | [[15-features/system/human-wait-window.md\|human-wait-window]] |

## System — Tool-Architecture (Hermes-Verbatim, Plan G v5/v6)

| Hermes-Standard | eaccode-Status | Notiz |
|---|---|---|
| G.1 Tool-Registry (toolsets, override) | done | [[15-features/system/tool-registry.md\|tool-registry]] |
| G.2 Tool-Search (BM25, deferred) | done | [[15-features/system/tool-search.md\|tool-search]] |
| G.3 Context-Overflow Defense 3-Layer | done | [[15-features/system/tool-result-storage.md\|tool-result-storage]] |
| G.4 Clarify-Tool (model→user) | done | [[15-features/system/clarify-tool.md\|clarify-tool]] |
| G.5 JSON-Schema-Sanitizer | done | [[15-features/system/schema-sanitizer.md\|schema-sanitizer]] |
| G.6 Environment-Probe | done | [[15-features/system/env-probe.md\|env-probe]] |
| G.7 Sub-Agent Live-Transcript + Redaction | done | [[15-features/system/live-transcript.md\|live-transcript]] |
| G.8 MCP-Description-Prompt-Injection-Scan | done | [[15-features/system/mcp-description-scan.md\|mcp-description-scan]] |
| G.9 Skill-AST-Audit (content-hash cache) | done | [[15-features/system/skills-guard.md\|skills-guard]] |
| G.10 Tool-Middlewares (pre_request + pre_execution) | done | [[15-features/system/middlewares.md\|middlewares]] |
| G.11 Denial-Breaker + Reset-on-Approve | done | [[15-features/system/denial-breaker.md\|denial-breaker]] |
| G.12 Tool-Output-Limits (configurable) | done | [[15-features/system/tool-output-limits.md\|tool-output-limits]] |
| **U1** Tool-Calls in DB persistieren | done | (Plan G v6, see `store.py`) |

## System — Hermes-Safety (Plan D) + Workspace (Plan H)

| Hermes-Feature | Status | Notiz |
|---|---|---|
| H1 Tirith Scanner (Binary + SHA-256 + Cosign) | done | [[15-features/system/tirith-security.md\|tirith-security]] |
| H2/H14/H15 file_safety (paths + sensitive dirs) | done | [[15-features/system/file_safety.md\|file_safety]] |
| H4/H5/H6 command_normalize + parser-limit + ~-fold | done | [[15-features/system/permissions.md\|permissions]] |
| H7 sudo-stdin-guard (8 patterns) | done | [[15-features/system/permissions.md\|permissions]] |
| H13/H20/H21/H24 runtime_context | done | [[15-features/system/permissions.md\|permissions]] |
| H16 WRITE_SAFE_ROOT env-var | done | [[15-features/system/file_safety.md\|file_safety]] |
| H18 path-security (devices, UNC, traversal) | done | [[15-features/system/path-security.md\|path-security]] |
| H22 write_approval (staged writes) | done | [[15-features/system/write-approval.md\|write-approval]] |
| H23 container-runner (Docker/chroot opt-in) | done (Stufe 3) | [[15-features/system/container.md\|container]] |
| H25 persistent blocked-list | done | [[15-features/system/blocked-list.md\|blocked-list]] |
| H26 human_wait_window | done | [[15-features/system/human-wait-window.md\|human-wait-window]] |
| **Plan H.1** Soft-Sandbox (cwd-as-workspace) | done | [[15-features/system/workspace.md\|workspace]] |
| **Plan H.2** Permission-Bridge (`/approvals allow-path`) | done | [[15-features/system/workspace.md\|workspace]] |
| **Plan H.3** Container-Sandbox (opt-in) | done | [[15-features/system/container.md\|container]] |
| `run_command` komplett raus | done (08-18) | (siehe Commit `11faf9c`) |

## Agents

| Agent | Status | Phase | Notiz |
|---|---|---|---|
| Subagents (B5, Pool max 6 parallel) | done | B5 | [[15-features/system/subagents.md\|subagents]] · [[15-features/agents/README.md\|README]] |

---

*Stand: 2026-08-18 — 988 Tests grün · Plan A–D ✅ · Plan G v5/v6 ✅ · Plan H Stufe 1+2 ✅ · Hermes-Coverage ~95%*
