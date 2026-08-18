"""Test runtime_context (Phase 4, H13/H20/H21/H24)."""

from __future__ import annotations

import os

import pytest

from eaccode import runtime_context as rc


class TestCronContext:
    def test_cron_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(os, "isatty", lambda fd: True)
        monkeypatch.setenv("EACCODE_CRON", "1")
        assert rc.is_cron_context() is True

    def test_cron_via_no_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EACCODE_CRON", raising=False)
        monkeypatch.setattr(os, "isatty", lambda fd: False)
        assert rc.is_cron_context() is True

    def test_not_cron(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EACCODE_CRON", raising=False)
        monkeypatch.delenv("EACCODE_IN_CRON", raising=False)
        monkeypatch.setattr(os, "isatty", lambda fd: True)
        assert rc.is_cron_context() is False


class TestCronApprovalMode:
    def test_default_deny(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # No config => default deny
        from eaccode import config as cfg

        monkeypatch.setattr(cfg, "load_config", lambda: None)
        assert rc.get_cron_approval_mode() == "deny"


class TestYOLOFrozen:
    def test_freeze_yolo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Reset
        rc._YOLO_FROZEN = False
        rc.freeze_yolo_mode()
        assert rc._YOLO_FROZEN is True
        # YOLO env should not bring it back
        monkeypatch.setenv("EACCODE_YOLO", "1")
        assert rc.is_yolo_active() is False

    def test_unfreeze_yolo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        rc._YOLO_FROZEN = False
        monkeypatch.setenv("EACCODE_YOLO", "1")
        assert rc.is_yolo_active() is True
        rc.freeze_yolo_mode()
        assert rc.is_yolo_active() is False


class TestContainerContext:
    def test_not_container(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EACCODE_IN_CONTAINER", raising=False)
        assert rc.is_container_context() is False

    def test_container_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EACCODE_IN_CONTAINER", "1")
        assert rc.is_container_context() is True

    def test_container_skip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EACCODE_IN_CONTAINER", "1")
        assert rc.container_can_skip_guards() is True

    def test_container_skip_with_bind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EACCODE_IN_CONTAINER", "1")
        monkeypatch.setenv("EACCODE_HOST_PATH_BIND", "1")
        assert rc.container_can_skip_guards() is False
