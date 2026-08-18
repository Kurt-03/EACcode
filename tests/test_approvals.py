"""Tests for /approvals slash-commands (Plan H.minimal v4, Tag 1)."""

from __future__ import annotations

import io

import pytest

from eaccode import commands
from eaccode.workspace import Workspace, set_active_workspace


@pytest.fixture
def fresh_workspace(tmp_path, monkeypatch):
    """Reset to a tmp workspace before each test."""
    ws_obj = Workspace(root=tmp_path.resolve())
    set_active_workspace(ws_obj)
    yield ws_obj
    set_active_workspace(None)


class TestApprovalsAllowPath:
    def test_default_scope_is_session(self, fresh_workspace) -> None:
        out = io.StringIO()
        rc = commands.run_approvals_command(
            ["allow-path", "C:/Users/admin/Desktop"], stdout=out
        )
        assert rc == 0
        rules = fresh_workspace.list_rules()
        assert len(rules) == 1
        assert rules[0].scope == "session"
        assert rules[0].kind == "allow"

    def test_explicit_scope(self, fresh_workspace) -> None:
        out = io.StringIO()
        commands.run_approvals_command(
            ["allow-path", "C:/Users/admin/Desktop", "--always"], stdout=out
        )
        assert fresh_workspace.list_rules()[0].scope == "always"

    def test_missing_path_returns_error(self, fresh_workspace) -> None:
        out = io.StringIO()
        rc = commands.run_approvals_command(["allow-path"], stdout=out)
        assert rc == 1
        assert "Usage:" in out.getvalue()


class TestApprovalsDenyPath:
    def test_default_scope_is_session(self, fresh_workspace) -> None:
        out = io.StringIO()
        rc = commands.run_approvals_command(
            ["deny-path", "C:/Users/admin/secrets"], stdout=out
        )
        assert rc == 0
        rules = fresh_workspace.list_rules()
        assert len(rules) == 1
        assert rules[0].kind == "deny"

    def test_always_scope(self, fresh_workspace) -> None:
        out = io.StringIO()
        commands.run_approvals_command(
            ["deny-path", "C:/Users/admin/secrets", "--always"], stdout=out
        )
        assert fresh_workspace.list_rules()[0].scope == "always"


class TestApprovalsList:
    def test_empty_list(self, fresh_workspace) -> None:
        out = io.StringIO()
        commands.run_approvals_command(["list"], stdout=out)
        assert "No registered" in out.getvalue()

    def test_shows_allow_and_deny(self, fresh_workspace) -> None:
        commands.run_approvals_command(["allow-path", "C:/a", "--always"])
        commands.run_approvals_command(["deny-path", "C:/b", "--session"])
        out = io.StringIO()
        commands.run_approvals_command(["list"], stdout=out)
        text = out.getvalue()
        assert "Allow-paths:" in text
        assert "Deny-paths:" in text
        assert "C:/a" in text
        assert "C:/b" in text


class TestApprovalsReset:
    def test_removes_session_and_once_rules(self, fresh_workspace) -> None:
        commands.run_approvals_command(["allow-path", "C:/a", "--session"])
        commands.run_approvals_command(["allow-path", "C:/b", "--always"])
        out = io.StringIO()
        commands.run_approvals_command(["reset"], stdout=out)
        rules = fresh_workspace.list_rules()
        # Only always-scoped survive
        assert len(rules) == 1
        assert rules[0].scope == "always"


class TestApprovalsHelp:
    def test_help(self) -> None:
        out = io.StringIO()
        rc = commands.run_approvals_command(["help"], stdout=out)
        assert rc == 0
        assert "Usage:" in out.getvalue()

    def test_unknown_command(self) -> None:
        out = io.StringIO()
        rc = commands.run_approvals_command(["bogus"], stdout=out)
        assert rc == 1
        assert "Unknown" in out.getvalue()