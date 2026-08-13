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
Externe Tools über das Model Context Protocol anbinden: stdio + Streamable
HTTP (aktueller Standard), Tool-Discovery, Permission-Integration (C1).

## Implementierung (Standard-Stand 2026-08-13, Web-Recherche)
- `src/eaccode/mcp.py`:
  - **Streamable HTTP** (aktueller Standard seit 2025-03-26, ersetzt SSE;
    Removal-Deadline 2026) — `McpHttpClient`: ein Endpoint, POST JSON-RPC,
    Antwort JSON oder SSE-Stream, `Mcp-Session-Id`-Echo
  - **stdio**: `McpClient` (JSON-RPC über stdin/stdout, Thread-Timeout)
  - **SSE nur noch als Legacy** (`transport: sse` in der Config)
  - Protokoll-Version: `2026-07-28` (aktuelle Spec, RC; Server antworten
    mit ihrer Version)
- Server in config.yaml: `mcp.servers: {name: {command|url, transport}}`
- `eaccode mcp list|add|remove`; Tools heißen `mcp__<server>__<tool>`
  und laufen durch den PermissionManager (C1)
- `eaccode mcp import <file.json | inline-json>` — mcpServers-JSON
  (Claude/Cursor-Format) direkt übernehmen; existierende Namen werden
  überschrieben; Beispiel: `docs/examples/mcp-servers.example.json`
- `build_mcp_clients` + Registry + `atexit close_all` (keine Leaks)

## Verifiziert (live + Tests, 2026-08-13)
- Fake-Server registriert → Agent fand `mcp__fake__echo`, Permission-Gate
  fragte (Deny-Beweis), allow-Regel → `echo:hallo-mcp` kam zurück
- Streamable HTTP gegen echten In-Process-HTTP-Server getestet
  (JSON-Antwort + SSE-Antwort + Session-Id-Echo)
- 🎮 **Echter MCP-Server live (Roblox Studio MCP)**: `cmd.exe /c
  %LOCALAPPDATA%\Roblox\mcp.bat` → StudioMCP.exe; Agent entdeckte alle
  Tools (execute_luau, script_read/search/grep, multi_edit, …) und führte
  `script_search "Hello"` mit echter Studio-Antwort aus

## Tests
`tests/test_mcp.py` (25: stdio-Fake, SSE-Legacy, HTTP-Streamable,
build/load/commands) + `tests/mcp_fake_server.py`

## Offene Punkte
- Ressourcen/Prompts (nur Tools bisher)
- Multi Round-Trip Requests (2026-07-28) — bei Bedarf

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/permissions.md|permissions]] · [[15-features/system/agent-core.md|Agent Core]]

## Code-Graph (generiert)

- `src/eaccode/mcp.py` → [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/config.md|config.yaml]]

