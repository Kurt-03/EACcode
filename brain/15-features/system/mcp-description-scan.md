---
name: mcp-description-scan
type: system
status: done
phase: 08-18 plan-g-v5-g8
date: 2026-08-18
tags: [type/feature, feature/system, security, hermes]
---

# MCP Description Prompt-Injection Scan (G.8)

> Scannt MCP-Tool-Descriptions auf Prompt-Injection-Pattern, wenn der MCP-
> Client sich verbindet. High-Findings blockieren, Medium warnt, Low logged.

## Detection-Heuristiken

| Severity | Beispiel-Pattern |
|---|---|
| **HIGH** | "ignore previous instructions", "system: ...", direct role-injection |
| **MEDIUM** | "respond in JSON only", "your new instructions are ...", user-impersonation |
| **LOW** | "always", "must", unusual verb imperatives outside docstring norm |

## Public API

```python
@dataclass
class DescriptionFinding:
    rule_id: str
    severity: str   # HIGH | MEDIUM | LOW
    snippet: str    # truncated offending phrase

@dataclass
class DescriptionScanReport:
    server_name: str
    findings: list[DescriptionFinding]
    def is_clean: bool
    def format() -> str     # pretty
```

`scan_descriptions(server_name, tools: list[(name, description, schema)]) -> DescriptionScanReport`

## UX

Beim MCP-Connect: Banner mit `mcp_description_scan.format(report)`.
HIGH → Warn-Modal, User muss explizit approven.

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.8
- [[15-features/system/mcp-client.md|mcp-client]]
- Hermes source: pattern aus `_ref/hermes/tools/mcp_tool.py:_scan_mcp_description`

## Tests

`tests/test_mcp_description_scan.py` — Synthetic clean + dirty descriptions,
Severity-Triage, Real-MCP-Server-Files in `tests/fixtures/mcp_payloads/`.
