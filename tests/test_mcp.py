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
