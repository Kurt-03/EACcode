---
status: done
name: command-mcp
type: command
phase: C3
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /mcp

## Zweck
MCP-Server im REPL verwalten (CLI-Äquivalent: `eaccode mcp …`).

## Syntax
```
/mcp list
/mcp add <name> --command <cmd> [--args …]     # stdio
/mcp add <name> --url <url> [--transport sse]  # Streamable HTTP / SSE
/mcp import <datei.json | inline-json>         # mcpServers-Format
/mcp remove <name>
```

## Details
- Server-Konfiguration in `config.yaml` unter `mcp.servers`
- Entdeckte Tools heißen `mcp__<server>__<tool>` und laufen durch den
  Permission-Gate (mutierend → ask)
- Import akzeptiert Claude/Cursor-`mcpServers`-JSON (Datei oder Inline);
  existierende Server werden überschrieben

## Verknüpft
[[15-features/system/mcp-client.md|mcp-client]] · [[15-features/commands/README.md|README]]
