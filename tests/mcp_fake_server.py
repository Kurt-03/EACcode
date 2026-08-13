"""Fake MCP server for tests: answers initialize/tools/list/tools/call over stdio."""
import json
import sys

TOOLS = [
    {
        "name": "echo",
        "description": "Echoes the given text",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}},
    },
    {
        "name": "boom",
        "description": "Always fails",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

for line in sys.stdin:
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        continue
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fake-server", "version": "1.0"},
            },
        }
    elif method == "tools/list":
        response = {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    elif method == "tools/call":
        params = message.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        if tool_name == "echo":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"echo:{arguments.get('text', '')}"}]
                },
            }
        elif tool_name == "boom":
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": "kaputt"}], "isError": True},
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": f"unknown:{tool_name}"}]},
            }
    else:
        continue  # notifications have no id
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()
