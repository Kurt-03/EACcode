---
name: mcp-client
type: system
status: active
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
  NEWLINE-delimited), initialize → tools/list → tools/call
- Server in config.yaml: `mcp.servers: {name: {command, args}}`
- `eaccode mcp list|add|remove` + Agent-Tools aus Discovery
- MCP-Tools laufen durch den PermissionManager (C1)

## Verifiziert (live, 2026-08-13)
- (wird beim Live-Test ergänzt)

## Tests
`tests/test_mcp.py` (Fake-MCP-Server als subprocess)

## Offene Punkte
- SSE-Transport
- Ressourcen/Prompts (nur Tools bisher)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/permissions.md|Permissions]] · [[15-features/system/agent-core.md|Agent Core]]
