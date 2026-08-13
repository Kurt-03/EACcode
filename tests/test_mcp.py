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


def _iso_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate config AND data dir (commands read/write config_dir()!)."""
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    cfg.ensure_config()


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


class TestHttpClient:
    """Streamable HTTP transport against an in-process JSON/SSE server."""

    @pytest.fixture
    def http_server(self) -> Any:
        import json as json_mod
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        state: dict[str, Any] = {"mode": "json", "session_seen": []}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                payload = json_mod.loads(self.rfile.read(length))
                method = payload.get("method")
                if "Mcp-Session-Id" in self.headers:
                    state["session_seen"].append(self.headers["Mcp-Session-Id"])
                if method == "initialize":
                    result = {
                        "protocolVersion": "2026-07-28",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "http-fake", "version": "1.0"},
                    }
                elif method == "tools/list":
                    result = {
                        "tools": [
                            {
                                "name": "http_echo",
                                "description": "http echo",
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
                            {"type": "text", "text": f"http:{arguments.get('text', '')}"}
                        ]
                    }
                else:
                    result = {}
                message = {"jsonrpc": "2.0", "id": payload.get("id"), "result": result}
                self.send_response(200)
                self.send_header("Mcp-Session-Id", "sess-1")
                if state["mode"] == "sse":
                    self.send_header("Content-Type", "text/event-stream")
                    body = f"event: message\ndata: {json_mod.dumps(message)}\n\n"
                else:
                    self.send_header("Content-Type", "application/json")
                    body = json_mod.dumps(message)
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
                self.wfile.flush()

            def log_message(self, *args: Any) -> None:
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield (
            f"http://127.0.0.1:{server.server_port}/mcp",
            state,
        )
        server.shutdown()

    def test_http_json_response(self, http_server: Any) -> None:
        url, state = http_server
        client = mcp.McpHttpClient(McpServer("remote", url=url))
        try:
            info = client.initialize()
            assert info["serverInfo"]["name"] == "http-fake"
            names = [t["name"] for t in client.list_tools()]
            assert names == ["http_echo"]
            assert client.call_tool("http_echo", {"text": "hi"}) == "http:hi"
            assert state["session_seen"]  # session id echoed on follow-ups
        finally:
            client.close()

    def test_http_sse_response(self, http_server: Any) -> None:
        url, state = http_server
        state["mode"] = "sse"
        client = mcp.McpHttpClient(McpServer("remote", url=url))
        try:
            info = client.initialize()
            assert info["serverInfo"]["name"] == "http-fake"
            assert client.call_tool("http_echo", {"text": "x"}) == "http:x"
        finally:
            client.close()

    def test_http_default_transport_selected(self, http_server: Any) -> None:
        url, _ = http_server
        conf = {"mcp": {"servers": {"remote": {"url": url}}}}
        clients = mcp.build_mcp_clients(conf)
        assert len(clients) == 1
        assert isinstance(clients[0], mcp.McpHttpClient)
        clients[0].close()

    def test_sse_transport_legacy_selected(self, http_server: Any) -> None:
        url, _ = http_server
        conf = {"mcp": {"servers": {"legacy": {"url": url, "transport": "sse"}}}}
        servers = mcp.load_servers(conf)
        assert servers[0].transport == "sse"


class TestImportCommand:
    @pytest.fixture
    def mcp_runner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
        _iso_config(tmp_path, monkeypatch)
        import io

        from eaccode.commands import run_mcp_command

        def run(*args: str) -> tuple[int, str]:
            stdout = io.StringIO()
            code = run_mcp_command(list(args), stdout=stdout)
            return code, stdout.getvalue()

        return run

    def test_import_inline_json(self, mcp_runner: Any) -> None:
        code, out = mcp_runner(
            "import",
            '{"mcpServers": {"inline_srv": {"command": "echo", '
            '"args": ["hi"]}, "remote": {"url": "http://x:1/sse", '
            '"transport": "sse"}}}',
        )
        assert code == 0
        assert "added 2" in out
        code, out = mcp_runner("list")
        assert "inline_srv" in out
        assert "remote" in out
        assert "transport: sse" in out

    def test_import_from_file(self, mcp_runner: Any, tmp_path: Path) -> None:
        json_file = tmp_path / "servers.json"
        json_file.write_text(
            '{"mcpServers": {"Roblox_Studio": {"command": "cmd.exe", '
            '"args": ["/c", "%LOCALAPPDATA%\\\\Roblox\\\\mcp.bat"]}}}',
            encoding="utf-8",
        )
        code, out = mcp_runner("import", str(json_file))
        assert code == 0
        assert "added 1" in out
        code, out = mcp_runner("list")
        assert "Roblox_Studio" in out
        assert "cmd.exe" in out

    def test_import_overwrites_and_skips(self, mcp_runner: Any) -> None:
        mcp_runner("add", "keep", "--command", "echo", "--args", "a")
        code, out = mcp_runner(
            "import",
            '{"mcpServers": {"keep": {"command": "new"}, '
            '"kaputt": {"args": ["x"]}}}',
        )
        assert code == 0
        assert "updated 1" in out
        assert "skipped 1" in out
        code, out = mcp_runner("list")
        assert "new" in out
        assert "kaputt" not in out

    def test_import_invalid_json(self, mcp_runner: Any) -> None:
        code, out = mcp_runner("import", "{kaputt")
        assert code == 1
        assert "invalid JSON" in out

    def test_import_missing_file(self, mcp_runner: Any) -> None:
        code, out = mcp_runner("import", "C:/definitely/not/here.json")
        assert code == 1
        assert "invalid JSON" in out


class TestMcpCommand:
    @pytest.fixture
    def mcp_runner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
        _iso_config(tmp_path, monkeypatch)
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
