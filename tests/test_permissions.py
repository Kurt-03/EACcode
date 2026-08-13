"""Tests for the permission system (Phase C1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eaccode import config as cfg
from eaccode import permissions
from eaccode.permissions import PermissionManager


@pytest.fixture
def perm_conf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    cfg.ensure_config()
    return {"permissions": {"mode": "ask", "allow": [], "deny": []}}


class TestModes:
    def test_default_ask_denies_without_handler(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        decision = manager.check("write_file", {"path": "x"})
        assert not decision.allow
        assert "no permission handler" in decision.reason

    def test_ask_handler_controls(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        manager.ask_handler = lambda name, args: name == "write_file"
        assert manager.check("write_file", {}).allow
        assert not manager.check("run_command", {}).allow

    def test_ask_readonly_tools_run_freely(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        assert manager.check("read_file", {}).allow  # no handler needed
        assert manager.check("current_time", {}).allow
        assert manager.check("web_search", {}).allow
        assert not manager.check("write_file", {}).allow  # mutating -> ask
        assert not manager.check("run_command", {}).allow
        assert not manager.check("spawn_subagent", {}).allow

    def test_allow_all(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "allow_all"
        manager = PermissionManager(perm_conf)
        assert manager.check("run_command", {"command": "rm -rf /"}).allow

    def test_deny_all(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "deny_all"
        manager = PermissionManager(perm_conf)
        decision = manager.check("read_file", {})
        assert not decision.allow
        assert "deny_all" in decision.reason

    def test_read_only_blocks_write_tools(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "read_only"
        manager = PermissionManager(perm_conf)
        assert manager.check("read_file", {}).allow
        assert manager.check("search_files", {}).allow
        assert not manager.check("write_file", {}).allow
        assert not manager.check("run_command", {}).allow
        assert not manager.check("create_skill", {}).allow
        assert not manager.check("memory_add", {}).allow


class TestRules:
    def test_deny_rule_wins_over_allow(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["mode"] = "allow_all"
        perm_conf["permissions"]["deny"] = [r"run_command"]
        manager = PermissionManager(perm_conf)
        assert not manager.check("run_command", {"command": "echo hi"}).allow
        assert manager.check("write_file", {"path": "x"}).allow

    def test_allow_rule_matches_arguments(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["allow"] = [r"run_command.*echo"]
        manager = PermissionManager(perm_conf)
        assert manager.check("run_command", {"command": "echo hallo"}).allow
        assert not manager.check("run_command", {"command": "del file"}).allow

    def test_deny_rule_matches_arguments(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["deny"] = [r"rm -rf"]
        manager = PermissionManager(perm_conf)
        assert not manager.check("run_command", {"command": "rm -rf /"}).allow

    def test_deny_rule_in_ask_mode(self, perm_conf: dict) -> None:
        perm_conf["permissions"]["deny"] = [r"write_file"]
        manager = PermissionManager(perm_conf)
        manager.ask_handler = lambda name, args: True
        assert not manager.check("write_file", {"path": "x"}).allow  # rule wins
        assert manager.check("run_command", {"command": "echo"}).allow

    def test_call_text_contains_arguments(self, perm_conf: dict) -> None:
        manager = PermissionManager(perm_conf)
        text = manager.call_text("run_command", {"command": "echo hi"})
        assert text == 'run_command {"command": "echo hi"}'


class TestModeHint:
    def test_read_only_hint(self) -> None:
        hint = permissions.mode_hint("read_only")
        assert "READ-ONLY" in hint
        assert "write_file" in hint

    def test_deny_all_hint(self) -> None:
        assert "DENY-ALL" in permissions.mode_hint("deny_all")

    def test_allow_all_hint(self) -> None:
        assert "AUTO-APPROVE" in permissions.mode_hint("allow_all")

    def test_ask_hint(self) -> None:
        assert "ASK" in permissions.mode_hint("ask")


class TestPersistence:
    def test_write_mode(self, perm_conf: dict) -> None:
        section = permissions.write_permissions_config(mode="read_only")
        assert section["mode"] == "read_only"
        assert cfg.load_config()["permissions"]["mode"] == "read_only"

    def test_write_rules_and_remove(self, perm_conf: dict) -> None:
        permissions.write_permissions_config(add_deny="rm -rf")
        permissions.write_permissions_config(add_allow="echo")
        section = cfg.load_config()["permissions"]
        assert section["deny"] == ["rm -rf"]
        assert section["allow"] == ["echo"]
        permissions.write_permissions_config(remove_deny="rm -rf")
        assert cfg.load_config()["permissions"]["deny"] == []

    def test_reset(self, perm_conf: dict) -> None:
        permissions.write_permissions_config(mode="deny_all", add_deny="x")
        section = permissions.write_permissions_config(reset=True)
        assert section == {"mode": "ask", "allow": [], "deny": []}

    def test_unknown_mode_rejected(self, perm_conf: dict) -> None:
        with pytest.raises(ValueError):
            permissions.write_permissions_config(mode="frobnicate")
