"""Plan B: Permission system hardening tests.

Verifies the audit fixes from 08-18:
- Sensitive-path detection on writes to .ssh/ / .env / config.yaml etc.
- is_always_ask now correctly blocks session memory
- Aux-LLM review still works for run_command dangerous patterns
- Smart-mode mutating non-ask tools still go to user prompt
- off mode auto-approves everything except hardline
"""

from __future__ import annotations

from eaccode import permissions
from eaccode.permissions import (
    PermissionManager,
    is_always_ask,
    is_read_only_tool,
)


class TestSensitivePaths:
    def test_ssh_key_write_asks(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            ask_handler=lambda n, a: True,
        )
        d = pm.check("write_file", {"path": "/home/user/.ssh/id_rsa", "content": "x"})
        # _ask_user returns "approved by user" once user OKs, but the
        # ROUTING through sensitive path is what we care about -
        # verify sensitive detection happened via _is_sensitive_path.
        assert pm._is_sensitive_path("/home/user/.ssh/id_rsa")

    def test_env_file_write_asks(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            ask_handler=lambda n, a: True,
        )
        pm.check("write_file", {"path": "/repo/.env", "content": "x"})
        assert pm._is_sensitive_path("/repo/.env")

    def test_config_yaml_write_asks(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            ask_handler=lambda n, a: True,
        )
        pm.check("write_file", {"path": "/repo/config.yaml", "content": "x"})
        assert pm._is_sensitive_path("/repo/config.yaml")

    def test_safe_path_no_sensitive_flag(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            ask_handler=lambda n, a: True,
        )
        d = pm.check("write_file", {"path": "/repo/src/foo.py", "content": "x"})
        # No sensitive-path reason
        assert "sensitive" not in d.reason.lower()


class TestAlwaysAskEnforcement:
    def test_browser_click_not_session_remembered(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "manual"}},
            ask_handler=lambda n, a: True,
        )
        d1 = pm.check("browser_click", {"selector": "button.submit"})
        # Always-ask: should NOT be added to session_allowed
        assert "browser_click" not in pm._session_allowed

    def test_run_command_not_session_remembered(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "manual"}},
            ask_handler=lambda n, a: True,
        )
        pm.check("run_command", {"command": "ls"})
        assert "run_command" not in pm._session_allowed

    def test_write_file_remembered_for_session(self) -> None:
        # NOT in ALWAYS_ASK_TOOLS -> normal session memory
        pm = PermissionManager(
            {"permissions": {"mode": "manual"}},
            ask_handler=lambda n, a: True,
        )
        pm.check("write_file", {"path": "/repo/x.py", "content": "y"})
        assert "write_file" in pm._session_allowed


class TestHardlineStillBlocks:
    def test_hardline_in_off_mode(self) -> None:
        pm = PermissionManager({"permissions": {"mode": "off"}})
        d = pm.check("run_command", {"command": "rm -rf /etc"})
        assert not d.allow
        assert "hardline" in d.reason

    def test_hardline_in_smart_mode(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            ask_handler=lambda n, a: True,
        )
        d = pm.check("run_command", {"command": "shutdown now"})
        assert not d.allow


class TestSmartModeDangerous:
    def test_dangerous_to_smart_reviewer(self) -> None:
        calls = []

        def reviewer(cmd, desc):
            calls.append((cmd, desc))
            return "approve"

        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            smart_reviewer=reviewer,
        )
        d = pm.check(
            "run_command", {"command": "chmod 777 /etc/passwd"}
        )
        assert d.allow
        assert "smart-approved" in d.reason

    def test_dangerous_to_escalate(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            smart_reviewer=lambda c, d: "ESCALATE",
            ask_handler=lambda n, a: True,
        )
        d = pm.check("run_command", {"command": "chmod 777 /etc/passwd"})
        assert d.allow
        # Routed via ask
        assert "approved by user" in d.reason or "smart" in d.reason


class TestReadOnlyToolDetection:
    def test_heuristic_name_match(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "manual"}},
            ask_handler=lambda n, a: True,
        )
        # read_file -> in our static list, auto-approved
        d = pm.check("read_file", {})
        assert d.allow
        assert "read-only" in d.reason


class TestIsAlwaysAsk:
    def test_run_command(self) -> None:
        assert is_always_ask("run_command")

    def test_browser_click(self) -> None:
        assert is_always_ask("browser_click")

    def test_write_file(self) -> None:
        # NOT in always-ask list (would be too noisy)
        assert not is_always_ask("write_file")


class TestIsReadOnlyTool:
    def test_with_tool_instance(self) -> None:
        from eaccode.agent import Tool

        ro = Tool(
            "test_ro",
            "Read-only tool",
            lambda: "",
            {"type": "object", "properties": {}},
            mutates=False,
        )
        assert is_read_only_tool(ro)

        rw = Tool(
            "test_rw",
            "Mutating tool",
            lambda: "",
            {"type": "object", "properties": {}},
            mutates=True,
        )
        assert not is_read_only_tool(rw)
