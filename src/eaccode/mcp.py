"""MCP client (Phase C3): connect external tools via the Model Context Protocol.

stdio transport with NEWLINE-delimited JSON-RPC 2.0. Servers are declared in
config.yaml under ``mcp.servers``; discovered tools become agent tools named
``mcp__<server>__<tool>`` and pass through the C1 permission gate.
"""

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass
from typing import Any

from eaccode import config as cfg
from eaccode.agent import Tool

MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_TIMEOUT = 30


@dataclass
class McpServer:
    name: str
    command: str
    args: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.args is None:
            self.args = []

    def to_dict(self) -> dict[str, Any]:
        return {"command": self.command, "args": self.args}


def load_servers(conf: dict[str, Any] | None = None) -> list[McpServer]:
    source = conf if conf is not None else cfg.load_config()
    servers = ((source or {}).get("mcp", {}) or {}).get("servers", {}) or {}
    return [
        McpServer(
            name=name,
            command=str(entry.get("command", "")),
            args=list(entry.get("args", []) or []),
        )
        for name, entry in servers.items()
        if isinstance(entry, dict) and entry.get("command")
    ]


class McpClient:
    """One stdio subprocess speaking MCP (JSON-RPC over newline-delimited JSON)."""

    def __init__(self, server: McpServer) -> None:
        self.server = server
        self._next_id = 1
        try:
            self._process = subprocess.Popen(
                [server.command, *server.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise McpError(
                f"cannot start mcp server '{server.name}': {exc}"
            ) from exc
        self._lock = threading.Lock()

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send one request and wait for its response (threaded timeout)."""
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        with self._lock:
            self._write(payload)
            response = self._read_with_timeout(request_id)
        if "error" in response:
            raise McpError(str(response["error"]))
        return response.get("result", {})

    def _write(self, payload: dict[str, Any]) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()

    def _read_with_timeout(self, request_id: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        errors: list[str] = []

        def reader() -> None:
            try:
                assert self._process.stdout is not None
                for line in self._process.stdout:
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if message.get("id") == request_id:
                        result["message"] = message
                        return
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(str(exc))

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        thread.join(MCP_TIMEOUT)
        if thread.is_alive():
            raise McpError(f"mcp server '{self.server.name}' timed out")
        if errors:
            raise McpError(f"mcp server '{self.server.name}' failed: {errors[0]}")
        return result.get("message", {})

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "eaccode", "version": "0.0.1"},
            },
        )
        # server notification: initialized (no id)
        with self._lock:
            self._write({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._request("tools/list")
        return list(result.get("tools", []) or [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        content = result.get("content", []) or []
        text = "\n".join(
            item.get("text", "") for item in content if item.get("type") == "text"
        )
        if result.get("isError"):
            return f"Error: mcp tool {name}: {text or 'failed'}"
        return text or "(no output)"

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()


class McpError(Exception):
    """Raised for MCP protocol/transport failures."""


def make_mcp_tools(clients: list[McpClient], conf: dict[str, Any] | None = None) -> list[Tool]:
    """Build agent tools from discovered MCP tools (mcp__<server>__<tool>)."""
    tools: list[Tool] = []
    for client in clients:
        try:
            client.initialize()
            discovered = client.list_tools()
        except McpError as exc:
            print(f"[mcp] skipping {client.server.name}: {exc}")
            continue
        for entry in discovered:
            name = str(entry.get("name", ""))
            if not name:
                continue
            description = str(entry.get("description", "") or "")
            schema = entry.get("inputSchema") or {"type": "object", "properties": {}}

            def make_call(
                tool_name: str = name, owner: McpClient = client
            ) -> Any:
                def call(**arguments: Any) -> str:
                    try:
                        return owner.call_tool(tool_name, arguments)
                    except McpError as exc:
                        return f"Error: {exc}"
                    except Exception as exc:
                        return f"Error: mcp tool failed: {exc}"

                return call

            tools.append(
                Tool(
                    name=f"mcp__{client.server.name}__{name}",
                    description=description,
                    func=make_call(),
                    parameters=schema,
                )
            )
    return tools
