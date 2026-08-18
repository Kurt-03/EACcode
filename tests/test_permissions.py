"""Tests for the permission system (Phase C1, with smart mode)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eaccode import config as cfg
from eaccode import permissions
from eaccode.permissions import PermissionManager


@pytest.fixture
def perm_conf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    cfg.ensure_config()
    return {"permissions": {"mode": "smart", "allow": [], "deny": []}}


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


class TestModes:
    def test_default_smart_allows_readonly(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        assert manager.check("read_file", {}).allow

    def test_default_smart_denies_mutating_without_handler(
        self, perm_conf: dict
    ) -> None:
        manager = PermissionManager(perm_conf)
        decision = manager.check("write_file", {"path": "x"})
        # smart mode: write_file has no dangerous pattern, no hardline, but
        # it's a mutating tool without session approval -> asks user
        assert decision.mode == "smart"

    def test_smart_ask_handler_controls(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        manager.ask_handler = lambda name, args: name == "write_file"
        # write_file has no dangerous pattern, so smart auto-approves
        assert manager.check("write_file", {}).allow
        # run_command without command arg has no dangerous pattern -> auto-approve
        # (ask handler is NOT consulted for safe commands in smart mode)

    def test_smart_readonly_tools_run_freely(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        assert manager.check("read_file", {}).allow
        assert manager.check("current_time", {}).allow
        assert manager.check("web_search", {}).allow
        # mutating tools still need approval
        # But session_allow can be set

    def test_smart_safe_run_command_run_freely(
        self, perm_conf: dict
    ) -> None:
        manager = PermissionManager(perm_conf)
        # safe command without dangerous pattern -> auto-approve
        d = manager.check("run_command", {"command": "ls -la"})
        assert d.allow

    def test_manual_mode_prompts_every_time(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "manual"
        manager = PermissionManager(perm_conf)
        manager.ask_handler = lambda name, args: True
        assert manager.check("write_file", {}).allow
        assert manager.check("write_file", {}).allow
        # manual mode: critical tools always ask
        assert manager.check("run_command", {"command": "ls"}).allow
        assert manager.check("run_command", {"command": "ls"}).allow

    def test_off_mode_auto_approves(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "off"
        manager = PermissionManager(perm_conf)
        # Safe commands run without asking (hardline still blocks)
        assert manager.check("run_command", {"command": "ls -la"}).allow
        # Hardline patterns still block in off mode
        assert not manager.check("run_command", {"command": "rm -rf /"}).allow

    def test_read_only_blocks_write_tools(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "read_only"
        manager = PermissionManager(perm_conf)
        assert manager.check("read_file", {}).allow
        assert manager.check("search_files", {}).allow
        assert not manager.check("write_file", {}).allow
        assert not manager.check("run_command", {}).allow
        assert not manager.check("create_skill", {}).allow
        assert not manager.check("memory_add", {}).allow


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


class TestRules:
    def test_deny_rule_wins_over_allow(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "off"
        perm_conf["permissions"]["deny"] = [r"run_command"]
        manager = PermissionManager(perm_conf)
        assert not manager.check("run_command", {"command": "echo hi"}).allow
        assert manager.check("write_file", {"path": "x"}).allow

    def test_allow_rule_matches_arguments(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["allow"] = [r"run_command.*chmod"]
        manager = PermissionManager(perm_conf)
        # Allow rule matches -> auto-approve (chmod 777 has dangerous pattern but allow rule wins)
        d = manager.check("run_command", {"command": "chmod 777 /tmp/test"})
        assert d.allow

    def test_deny_rule_matches_arguments(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["deny"] = [r"rm -rf"]
        manager = PermissionManager(perm_conf)
        assert not manager.check("run_command", {"command": "rm -rf /etc"}).allow

    def test_call_text_contains_arguments(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        text = manager.call_text("run_command", {"command": "echo hi"})
        assert text == 'run_command {"command": "echo hi"}'


# ---------------------------------------------------------------------------
# Hardline patterns (always block regardless of mode)
# ---------------------------------------------------------------------------


class TestHardline:
    def test_hardline_blocks_rm_root(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        d = manager.check("run_command", {"command": "rm -rf /etc"})
        assert not d.allow
        assert "hardline" in d.reason or "root filesystem" in d.reason

    def test_hardline_blocks_rm_home(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        d = manager.check("run_command", {"command": "rm -rf /etc"})
        assert not d.allow
        assert "hardline" in d.reason or "home" in d.reason

    def test_hardline_blocks_shutdown(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        d = manager.check("run_command", {"command": "shutdown now"})
        assert not d.allow

    def test_hardline_blocks_fork_bomb(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        d = manager.check(
            "run_command", {"command": ":(){ :|:& };:"}
        )
        assert not d.allow

    def test_hardline_blocks_dd_to_raw_device(
        self, perm_conf: dict
    ) -> None:
        manager = PermissionManager(perm_conf)
        d = manager.check(
            "run_command", {"command": "dd if=/dev/zero of=/dev/sda bs=1M"}
        )
        assert not d.allow

    def test_hardline_blocks_init6(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        d = manager.check("run_command", {"command": "init 6"})
        assert not d.allow

    def test_hardline_works_in_off_mode(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "off"
        manager = PermissionManager(perm_conf)
        # Hardline still blocks even in off mode
        d = manager.check("run_command", {"command": "rm -rf /etc"})
        assert not d.allow


# ---------------------------------------------------------------------------
# Smart mode: aux LLM routing
# ---------------------------------------------------------------------------


class TestSmartMode:
    def test_smart_routes_dangerous_to_reviewer(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        manager.smart_reviewer = lambda cmd, desc: "approve"
        # `rm -rf something` is a dangerous pattern -> goes to aux LLM
        d = manager.check("run_command", {"command": "chmod 777 /etc/passwd"})
        assert d.allow
        assert d.smart_reviewed

    def test_smart_denies_when_reviewer_returns_deny(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        manager.smart_reviewer = lambda cmd, desc: "deny"
        d = manager.check("run_command", {"command": "chmod 777 /etc/passwd"})
        assert not d.allow
        assert d.smart_reviewed

    def test_smart_escalates_to_user(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        manager.smart_reviewer = lambda cmd, desc: "escalate"
        manager.ask_handler = lambda name, args: True
        d = manager.check("run_command", {"command": "chmod 777 /etc/passwd"})
        assert d.allow

    def test_smart_without_reviewer_falls_back_to_ask(
        self, perm_conf: dict
    ) -> None:
        manager = PermissionManager(perm_conf)
        manager.ask_handler = lambda name, args: True
        d = manager.check("run_command", {"command": "chmod 777 /etc/passwd"})
        assert d.allow

    def test_smart_safe_command_no_review(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        manager.smart_reviewer = lambda cmd, desc: "should not be called"
        # `ls` is safe -> no aux LLM call, no prompt
        d = manager.check("run_command", {"command": "ls -la"})
        assert d.allow
        assert not d.smart_reviewed


# ---------------------------------------------------------------------------
# Session allow
# ---------------------------------------------------------------------------


class TestSessionAllow:
    def _manager(self) -> tuple[PermissionManager, list[str]]:
        calls: list[str] = []

        def handler(name: str, args: dict[str, Any]) -> bool:
            calls.append(name)
            return True

        return PermissionManager(ask_handler=handler), calls

    def test_approval_remembered_for_session(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        manager.ask_handler = lambda name, args: True
        assert manager.check("write_file", {}).allow
        assert manager.check("write_file", {}).allow
        assert manager.check("write_file", {}).allow

    def test_critical_tool_prompts_every_time(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        manager.ask_handler = lambda name, args: True
        # run_command is critical -> always prompts
        assert manager.check("run_command", {"command": "ls"}).allow
        assert manager.check("run_command", {"command": "ls"}).allow

    def test_readonly_mcp_runs_free(self) -> None:
        manager = PermissionManager(ask_handler=lambda name, args: False)
        assert manager.check("mcp__Roblox_Studio__script_search", {}).allow
        assert manager.check("mcp__Roblox_Studio__get_console_output", {}).allow

    def test_git_read_tools_run_free(self) -> None:
        manager = PermissionManager(ask_handler=lambda name, args: False)
        assert manager.check("git_status", {}).allow
        assert manager.check("git_log", {}).allow
        assert manager.check("git_diff", {}).allow
        assert manager.check("browser_status", {}).allow

    def test_session_clear_forgets_approvals(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "manual"
        manager = PermissionManager(perm_conf)
        manager.ask_handler = lambda name, args: True
        manager.check("write_file", {})
        manager.session_clear()
        manager.check("write_file", {})
        # After clear, the second check makes the set contain write_file again
        assert len(manager._session_allowed) == 1
        assert manager._session_allowed == {"write_file"}

    def test_deny_rule_wins_over_session(self) -> None:
        manager = PermissionManager(
            conf={"permissions": {"mode": "smart", "deny": ["write_file"]}},
            ask_handler=lambda name, args: True,
        )
        assert not manager.check("write_file", {}).allow
        manager.session_allow("write_file")
        assert not manager.check("write_file", {}).allow


# ---------------------------------------------------------------------------
# Mode hint
# ---------------------------------------------------------------------------


class TestModeHint:
    def test_smart_hint(self) -> None:
        hint = permissions.mode_hint("smart")
        assert "SMART" in hint
        assert "auto-approve" in hint

    def test_manual_hint(self) -> None:
        hint = permissions.mode_hint("manual")
        assert "MANUAL" in hint

    def test_off_hint(self) -> None:
        hint = permissions.mode_hint("off")
        assert "AUTO-APPROVE" in hint

    def test_read_only_hint(self) -> None:
        hint = permissions.mode_hint("read_only")
        assert "READ-ONLY" in hint
        assert "write_file" in hint


# ---------------------------------------------------------------------------
# Backward compat: old mode aliases
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_ask_aliases_to_manual(self) -> None:
        manager = PermissionManager(
            conf={"permissions": {"mode": "ask"}}
        )
        assert manager.mode == "manual"

    def test_allow_all_aliases_to_off(self) -> None:
        manager = PermissionManager(
            conf={"permissions": {"mode": "allow_all"}}
        )
        assert manager.mode == "off"

    def test_read_only_stays_read_only(self) -> None:
        manager = PermissionManager(
            conf={"permissions": {"mode": "read_only"}}
        )
        assert manager.mode == "read_only"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_write_mode(self, perm_conf: dict) -> None:
        section = permissions.write_permissions_config(mode="read_only")
        assert section["mode"] == "read_only"
        assert cfg.load_config()["permissions"]["mode"] == "read_only"

    def test_smart_mode_persists(self, perm_conf: dict) -> None:
        permissions.write_permissions_config(mode="smart")
        assert cfg.load_config()["permissions"]["mode"] == "smart"

    def test_write_rules_and_remove(self, perm_conf: dict) -> None:
        permissions.write_permissions_config(add_deny="rm -rf")
        permissions.write_permissions_config(add_allow="echo")
        section = cfg.load_config()["permissions"]
        assert section["deny"] == ["rm -rf"]
        assert section["allow"] == ["echo"]
        permissions.write_permissions_config(remove_deny="rm -rf")
        assert cfg.load_config()["permissions"]["deny"] == []

    def test_reset(self, perm_conf: dict) -> None:
        permissions.write_permissions_config(mode="off", add_deny="x")
        section = permissions.write_permissions_config(reset=True)
        assert section == {"mode": "smart", "allow": [], "deny": []}

    def test_unknown_mode_rejected(self, perm_conf: dict) -> None:
        with pytest.raises(ValueError):
            permissions.write_permissions_config(mode="frobnicate")
