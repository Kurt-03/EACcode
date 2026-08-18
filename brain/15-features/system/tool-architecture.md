---
name: tool-architecture
type: system
status: done
phase: 08-18 plan-g-v5
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# Tool Architecture (Hermes-Verbatim, Plan G v5)

> 1:1 Hermes-Coverage der Tool-Architektur. 10 neue Module + ~250 neue Tests.

## Was Plan G v5 abgedeckt hat

| # | Hermes-Standard | eaccode-Status |
|---|---|---|
| G.1 | Tool-Registry mit Toolsets + check_fn + override | done (`registry.py`) |
| G.2 | Tool-Search Subsystem (BM25, deferred tools) | done (`tool_search.py`) |
| G.3 | Context-Overflow Defense 3-Layer (persist + budget) | done (`tool_result_storage.py`) |
| G.4 | Clarify-Tool (model fragen statt raten) | done (`clarify_tool.py`) |
| G.5 | JSON-Schema-Sanitization (Provider-Kompatibilität) | done (`schema_sanitizer.py`) |
| G.6 | Environment-Probe (Python/pip/PEP668/git) | done (`env_probe.py`) |
| G.7 | Sub-Agent-Live-Transcript mit Secret-Redaction | done (`live_transcript.py`) |
| G.8 | MCP-Description-Prompt-Injection-Scan | done (`mcp_description_scan.py`) |
| G.9 | Skill-AST-Audit vor install | done (`skills_guard.py`) |
| G.10 | Tool-Middlewares (pre_request + pre_execution) | done (`middlewares.py`) |
| G.11 | Permission-Fixes (Denial-Breaker + Reset) | done (`denial_breaker.py`) |
| G.12 | Tool-Output-Limits (configurable truncation) | done (`tool_output_limits.py`) |

## Was Plan G v6 abgedeckt hat (User-Impact-Fixes)

| # | Hermes-Standard | eaccode-Status |
|---|---|---|
| **U1** | **Tool-Calls in DB persistieren** | done (`store.py` schema migration) |

## Endstand

- **988 Tests grün** (Stand 08-18, Plan H Audit-Phase `146ffce`)
- 13 neue Module, ~4500 LOC neu
- Plan G v5 + Plan G v6 komplett abgearbeitet
- **Plan H Stufe 1 + Stufe 2:** Workspace-Sandbox (`workspace.py`) +
  `/approvals allow-path` (`approvals_store.py` + `path_security.py`)
- Hermes-Inventar-Coverage: ~95%

## Reference

- Plan: `.hermes/plans/2026-08-18_180301-aux-llm-coverage.md`
- Hermes source: `_ref/hermes/tools/registry.py`, `tool_search.py`,
  `tool_result_storage.py`, `clarify_tool.py`, `schema_sanitizer.py`,
  `env_probe.py`, `delegation_live_log.py`, `mcp_tool.py`,
  `skills_guard.py`, `approval.py`

## Modul-Notizen (jedes Tool-G-Modul einzeln)

- [[15-features/system/tool-registry.md|tool-registry]] · [[15-features/system/tool-search.md|tool-search]] · [[15-features/system/tool-result-storage.md|tool-result-storage]] · [[15-features/system/tool-output-limits.md|tool-output-limits]] · [[15-features/system/middlewares.md|middlewares]] · [[15-features/system/clarify-tool.md|clarify-tool]] · [[15-features/system/schema-sanitizer.md|schema-sanitizer]] · [[15-features/system/env-probe.md|env-probe]] · [[15-features/system/live-transcript.md|live-transcript]] · [[15-features/system/mcp-description-scan.md|mcp-description-scan]] · [[15-features/system/skills-guard.md|skills-guard]] · [[15-features/system/denial-breaker.md|denial-breaker]] · [[15-features/system/human-wait-window.md|human-wait-window]] · [[15-features/system/blocked-list.md|blocked-list]]

## Code-Graph (generiert)

- `src/eaccode/blocked.py` → [[15-features/system/config.md|config.yaml]]

