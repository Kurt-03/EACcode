---
name: mcp-client
type: system
status: done
phase: C3
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: MCP-Client (C3)

## Zweck
Externe Tools über das Model Context Protocol anbinden: stdio-Server
(SSE später), Tool-Discovery, Permission-Integration (C1).

## Implementierung
- `src/eaccode/mcp.py` — `McpClient` (JSON-RPC 2.0 über stdin/stdout,
  NEWLINE-delimited, Thread-Timeout 30 s, McpError)
- Server in config.yaml: `mcp.servers: {name: {command, args}}`
- `eaccode mcp list|add|remove`; Tools heißen `mcp__<server>__<tool>`
  und laufen durch den PermissionManager (C1)
- build_agent startet konfigurierte Server und entdeckt Tools

## Verifiziert (live, 2026-08-13)
- Fake-Server registriert → Agent fand `mcp__fake__echo`, Permission-Gate
  fragte (Deny-Beweis), allow-Regel → `echo:hallo-mcp` kam zurück
- SSE-Client gegen In-Process-SSE-Server getestet (initialize/call)

## Tests
`tests/test_mcp.py` (17, inkl. Fake-Server-Subprocess + SSE-Server-Fixture)
+ `tests/mcp_fake_server.py`

## Offene Punkte
- Ressourcen/Prompts (nur Tools bisher)
- SSE: Notifications werden übersprungen (Request/Response-only)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/permissions.md|Permissions]] · [[15-features/system/agent-core.md|Agent Core]]
