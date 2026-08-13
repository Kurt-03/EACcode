"""Tests for the MCP client (Phase C3)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from eaccode import config as cfg
from eaccode import mcp
from eaccode.mcp import McpClient, McpServer

FAKE_SERVER = [sys.executable, str(Path(__file__).parent / "mcp_fake_server.py")]


@pytest.fixture
def mcp_conf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    return {
        "mcp": {
            "servers": {
                "fake": {"command": FAKE_SERVER[0], "args": [FAKE_SERVER[1]]}
            }
        }
    }


class TestClient:
    def test_initialize_and_list_tools(self, mcp_conf: dict) -> None:
        client = McpClient(McpServer("fake", FAKE_SERVER[0], [FAKE_SERVER[1]]))
        try:
            info = client.initialize()
            assert info["serverInfo"]["name"] == "fake-server"
            names = [t["name"] for t in client.list_tools()]
            assert "echo" in names
            assert "boom" in names
        finally:
            client.close()

    def test_call_tool(self, mcp_conf: dict) -> None:
        client = McpClient(McpServer("fake", FAKE_SERVER[0], [FAKE_SERVER[1]]))
        try:
            client.initialize()
            out = client.call_tool("echo", {"text": "hallo"})
            assert out == "echo:hallo"
        finally:
            client.close()

    def test_call_tool_error_flag(self, mcp_conf: dict) -> None:
        client = McpClient(McpServer("fake", FAKE_SERVER[0], [FAKE_SERVER[1]]))
        try:
            client.initialize()
            out = client.call_tool("boom", {})
            assert "Error" in out
            assert "kaputt" in out
        finally:
            client.close()

    def test_missing_server_command_raises(self, mcp_conf: dict) -> None:
        with pytest.raises(mcp.McpError):
            McpClient(McpServer("ghost", "definitely-not-a-command-xyz"))


class TestTools:
    def test_make_mcp_tools(self, mcp_conf: dict) -> None:
        clients = [McpClient(McpServer("fake", FAKE_SERVER[0], [FAKE_SERVER[1]]))]
        try:
            tools = mcp.make_mcp_tools(clients)
            names = {tool.name for tool in tools}
            assert "mcp__fake__echo" in names
            assert "mcp__fake__boom" in names
            echo = next(t for t in tools if t.name == "mcp__fake__echo")
            assert echo.func(text="hi") == "echo:hi"
        finally:
            for client in clients:
                client.close()

    def test_load_servers_from_config(self, mcp_conf: dict) -> None:
        servers = mcp.load_servers(mcp_conf)
        assert len(servers) == 1
        assert servers[0].name == "fake"
        assert servers[0].command == FAKE_SERVER[0]

    def test_load_servers_ignores_invalid(self, mcp_conf: dict) -> None:
        mcp_conf["mcp"]["servers"]["kaputt"] = {"command": ""}
        servers = mcp.load_servers(mcp_conf)
        assert [s.name for s in servers] == ["fake"]


class TestSseClient:
    """SSE transport against a minimal in-process SSE server."""

    @pytest.fixture
    def sse_server(self) -> Any:
        import json as json_mod
        import threading
        import time
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(b"event: endpoint\ndata: /message?session_id=abc\n\n")
                self.wfile.flush()
                time.sleep(30)  # keep the stream open until the test ends

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                payload = json_mod.loads(self.rfile.read(length))
                method = payload.get("method")
                if method == "initialize":
                    result = {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "sse-fake", "version": "1.0"},
                    }
                elif method == "tools/list":
                    result = {
                        "tools": [
                            {
                                "name": "sse_echo",
                                "description": "sse echo",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"text": {"type": "string"}},
                                },
                            }
                        ]
                    }
                elif method == "tools/call":
                    arguments = payload.get("params", {}).get("arguments", {})
                    result = {
                        "content": [
                            {"type": "text", "text": f"sse:{arguments.get('text', '')}"}
                        ]
                    }
                else:
                    result = {}
                message = {"jsonrpc": "2.0", "id": payload.get("id"), "result": result}
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                body = f"event: message\ndata: {json_mod.dumps(message)}\n\n"
                self.wfile.write(body.encode("utf-8"))
                self.wfile.flush()

            def log_message(self, *args: Any) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{server.server_port}/sse"
        server.shutdown()

    def test_sse_initialize_and_call(self, sse_server: str) -> None:
        sse = mcp.McpSseClient(McpServer("sse", url=sse_server))
        try:
            info = sse.initialize()
            assert info["serverInfo"]["name"] == "sse-fake"
            names = [t["name"] for t in sse.list_tools()]
            assert names == ["sse_echo"]
            assert sse.call_tool("sse_echo", {"text": "hi"}) == "sse:hi"
        finally:
            sse.close()

    def test_sse_make_mcp_tools(self, sse_server: str) -> None:
        client = mcp.McpSseClient(McpServer("sse", url=sse_server))
        try:
            tools = mcp.make_mcp_tools([client])
            assert "mcp__sse__sse_echo" in {t.name for t in tools}
        finally:
            client.close()

    def test_load_servers_url(self) -> None:
        conf = {"mcp": {"servers": {"remote": {"url": "http://localhost:1/sse"}}}}
        servers = mcp.load_servers(conf)
        assert servers[0].name == "remote"
        assert servers[0].url == "http://localhost:1/sse"
        assert not servers[0].command


class TestMcpCommand:
    @pytest.fixture
    def mcp_runner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        import io

        from eaccode.commands import run_mcp_command

        def run(*args: str) -> tuple[int, str]:
            stdout = io.StringIO()
            code = run_mcp_command(list(args), stdout=stdout)
            return code, stdout.getvalue()

        return run

    def test_list_empty(self, mcp_runner: Any) -> None:
        code, out = mcp_runner("list")
        assert code == 0
        assert "no servers" in out

    def test_add_remove(self, mcp_runner: Any) -> None:
        code, out = mcp_runner("add", "fake", "--command", FAKE_SERVER[0], "--args", FAKE_SERVER[1])
        assert code == 0
        assert "added" in out
        code, out = mcp_runner("list")
        assert "fake" in out
        code, out = mcp_runner("remove", "fake")
        assert code == 0
        assert "removed" in out
        code, out = mcp_runner("list")
        assert "no servers" in out
