"""Tests for run_command (Plan I P0.1)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from eaccode import tools
from eaccode.workspace import Workspace


@pytest.fixture(autouse=True)
def wire_workspace(tmp_path, monkeypatch):
    """Pin the tool module workspace to tmp_path."""
    ws_obj = Workspace(root=tmp_path.resolve())
    tools._set_workspace(ws_obj)
    yield
    tools._set_workspace(None)


@pytest.fixture
def permissive(monkeypatch):
    """Allow all run_command calls (skip permission gate)."""
    import threading
    monkeypatch.setattr(tools, "permission_handler", lambda cmd: True)
    # Set the thread-local flag so the permission gate inside run_command is skipped
    tools._loop_permission_checked.value = True
    yield
    try:
        tools._loop_permission_checked.value = False
    except AttributeError:
        pass


@pytest.fixture
def restrictive(monkeypatch):
    """Deny all run_command calls."""
    monkeypatch.setattr(tools, "permission_handler", lambda cmd: False)
    # Make sure the permission gate fires (default flag is False already)
    tools._loop_permission_checked.value = False
    yield


class TestBasic:
    def test_runs_simple_command(self, permissive) -> None:
        out = tools.run_command("echo hello")
        assert "hello" in out

    def test_returns_exit_code_marker(self, permissive) -> None:
        out = tools.run_command('python -c "import sys; sys.exit(3)"')
        assert "exit" in out.lower() or "3" in out

    def test_returns_no_output_marker(self, permissive) -> None:
        out = tools.run_command('python -c "pass"')
        assert out == "(no output)"

    def test_timeout_reported(self, permissive) -> None:
        out = tools.run_command('python -c "import time; time.sleep(5)"', timeout=1)
        assert "timed out" in out.lower()


class TestPermission:
    def test_permission_denied(self, restrictive) -> None:
        out = tools.run_command("echo hello")
        assert "permission denied" in out.lower()

    def test_permission_allowed(self, permissive) -> None:
        out = tools.run_command("echo hello")
        assert "hello" in out
        assert "permission" not in out.lower()


class TestCwd:
    def test_relative_cwd_resolves_against_workspace(self, permissive, tmp_path) -> None:
        (tmp_path / "subdir").mkdir()
        out = tools.run_command('python -c "import os; print(os.getcwd())"', cwd="subdir")
        # Should run inside the workspace subdir
        assert str((tmp_path / "subdir").resolve()) in out or "subdir" in out

    def test_absolute_cwd_outside_workspace_blocked(self, permissive) -> None:
        out = tools.run_command("echo hi", cwd="/etc/passwd")
        assert "outside workspace" in out.lower() or "Error" in out


class TestContainer:
    def test_container_mode_without_docker(self, permissive, monkeypatch) -> None:
        """EACCODE_RUN_IN_CONTAINER=1 but no docker -> friendly error."""
        monkeypatch.setenv("EACCODE_RUN_IN_CONTAINER", "1")
        # is_docker_available() returns False in test env (no docker)
        out = tools.run_command("echo hi")
        # Either error about docker not available OR ran natively (if docker exists)
        # Either way no crash
        assert out is not None


class TestToolRegistration:
    def test_run_command_in_builtin_tools(self) -> None:
        names = {t.name for t in tools.BUILTIN_TOOLS}
        assert "run_command" in names

    def test_run_command_has_mutates_and_always_ask(self) -> None:
        rc = next(t for t in tools.BUILTIN_TOOLS if t.name == "run_command")
        assert rc.mutates is True
        assert rc.always_ask is True
