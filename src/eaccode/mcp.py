"""MCP client (Phase C3): external tools via the Model Context Protocol.

Transports:
- stdio: NEWLINE-delimited JSON-RPC 2.0 over a subprocess
- SSE:   GET /sse for endpoint+session, POST JSON-RPC per request

Servers are declared in config.yaml under ``mcp.servers`` (``command`` for
stdio, ``url`` for SSE). Discovered tools become agent tools named
``mcp__<server>__<tool>`` and pass through the C1 permission gate.
"""

from __future__ import annotations

import atexit
import contextlib
import json
import subprocess
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from eaccode import config as cfg
from eaccode.agent import Tool

MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_TIMEOUT = 30

_CLIENTS: list[McpClientBase] = []


def _register(client: McpClientBase) -> None:
    _CLIENTS.append(client)


def close_all() -> None:
    """Close every opened MCP client (atexit + explicit cleanup)."""
    for client in _CLIENTS:
        with contextlib.suppress(Exception):
            client.close()
    _CLIENTS.clear()


atexit.register(close_all)


@dataclass
class McpServer:
    name: str
    command: str = ""
    args: list[str] = None  # type: ignore[assignment]
    url: str = ""

    def __post_init__(self) -> None:
        if self.args is None:
            self.args = []

    def to_dict(self) -> dict[str, Any]:
        entry: dict[str, Any] = {}
        if self.command:
            entry["command"] = self.command
            entry["args"] = self.args
        if self.url:
            entry["url"] = self.url
        return entry


def load_servers(conf: dict[str, Any] | None = None) -> list[McpServer]:
    source = conf if conf is not None else cfg.load_config()
    servers = ((source or {}).get("mcp", {}) or {}).get("servers", {}) or {}
    result: list[McpServer] = []
    for name, entry in servers.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("url"):
            result.append(McpServer(name=name, url=str(entry["url"])))
        elif entry.get("command"):
            result.append(
                McpServer(
                    name=name,
                    command=str(entry["command"]),
                    args=list(entry.get("args", []) or []),
                )
            )
    return result


class McpError(Exception):
    """Raised for MCP protocol/transport failures."""


class McpClientBase:
    """Shared MCP protocol logic (initialize / list_tools / call_tool)."""

    server: McpServer

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "eaccode", "version": "0.0.1"},
            },
        )
        with contextlib.suppress(Exception):  # notifications are best-effort
            self._notify("notifications/initialized")
        return result

    def _notify(self, method: str) -> None:
        raise NotImplementedError

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
        raise NotImplementedError


class McpClient(McpClientBase):
    """stdio transport: JSON-RPC over newline-delimited JSON on stdin/stdout."""

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
        _register(self)

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
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

    def _notify(self, method: str) -> None:
        with self._lock:
            self._write({"jsonrpc": "2.0", "method": method})

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

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()


def _parse_sse(text: str) -> list[tuple[str, str]]:
    """Parse SSE event/data pairs (accumulated data lines per event)."""
    events: list[tuple[str, str]] = []
    event, data = "message", ""
    for line in text.splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data += line[5:].strip()
        elif not line.strip() and data.strip():
            events.append((event, data.strip()))
            event, data = "message", ""
    if data.strip():
        events.append((event, data.strip()))
    return events


class McpSseClient(McpClientBase):
    """SSE transport: GET /sse for the endpoint, POST JSON-RPC requests."""

    def __init__(self, server: McpServer) -> None:
        self.server = server
        self._next_id = 1
        self._stream: Any = None
        self._endpoint = ""
        self._connect()
        _register(self)

    def _connect(self) -> None:
        try:
            self._stream = urllib.request.urlopen(self.server.url, timeout=10)
            endpoint_path = ""
            while endpoint_path == "":
                line = self._stream.readline()
                if not line:
                    break
                if line.startswith(b"data:"):
                    endpoint_path = line[5:].strip().decode("utf-8", "replace")
            if not endpoint_path:
                raise McpError(
                    f"mcp server '{self.server.name}': no endpoint from SSE stream"
                )
            self._endpoint = urllib.parse.urljoin(self.server.url, endpoint_path)
        except OSError as exc:
            raise McpError(
                f"cannot connect to mcp server '{self.server.name}': {exc}"
            ) from exc

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=MCP_TIMEOUT) as response:
                body = response.read().decode("utf-8", "replace")
        except OSError as exc:
            raise McpError(
                f"mcp server '{self.server.name}' request failed: {exc}"
            ) from exc
        for event, data in _parse_sse(body):
            if event != "message":
                continue
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise McpError(str(message["error"]))
                return message.get("result", {})
        raise McpError(f"mcp server '{self.server.name}': no matching response")

    def _notify(self, method: str) -> None:
        # SSE POSTs are request/response; notifications are skipped (best-effort)
        del method

    def close(self) -> None:
        if self._stream is not None:
            with contextlib.suppress(Exception):
                self._stream.close()
            self._stream = None


def build_mcp_clients(conf: dict[str, Any] | None = None) -> list[McpClientBase]:
    """Start one client per configured server (stdio or SSE)."""
    clients: list[McpClientBase] = []
    for server in load_servers(conf):
        try:
            clients.append(
                McpSseClient(server) if server.url else McpClient(server)
            )
        except McpError as exc:
            print(f"[mcp] skipping {server.name}: {exc}")
    return clients


def make_mcp_tools(clients: list[McpClientBase]) -> list[Tool]:
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
                tool_name: str = name, owner: McpClientBase = client
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
