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

- 877 Tests grün, 4 skipped
- 13 neue Module, ~4500 LOC neu
- Plan G v5 + Plan G v6 komplett abgearbeitet
- Hermes-Inventar-Coverage: ~95%

## Reference

- Plan: `.hermes/plans/2026-08-18_180301-aux-llm-coverage.md`
- Hermes source: `_ref/hermes/tools/registry.py`, `tool_search.py`, `tool_result_storage.py`, `clarify_tool.py`, `schema_sanitizer.py`, `env_probe.py`, `delegation_live_log.py`, `mcp_tool.py`, `skills_guard.py`, `approval.py`
