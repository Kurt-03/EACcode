"""Tests for container backend (Plan H Stufe 3, Hermes-Verbatim analog)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from eaccode import container as ct
from eaccode.container import (
    BACKEND_AUTO,
    BACKEND_DOCKER,
    BACKEND_NONE,
    ContainerConfig,
    ContainerHandle,
    _cleanup_inactive_containers,
    has_host_access_danger,
    is_docker_available,
)


@pytest.fixture
def fake_docker(monkeypatch):
    """Make shutil.which('docker') return a fake path."""
    monkeypatch.setattr(ct.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)


@pytest.fixture
def no_docker(monkeypatch):
    """Make shutil.which('docker') return None."""
    monkeypatch.setattr(ct.shutil, "which", lambda name: None)


class TestDockerAvailable:
    def test_with_docker(self, fake_docker) -> None:
        assert is_docker_available() is True

    def test_without_docker(self, no_docker) -> None:
        assert is_docker_available() is False


class TestStartContainer:
    def test_no_docker_raises(self, no_docker) -> None:
        config = ContainerConfig()
        with pytest.raises(RuntimeError, match="docker not available"):
            ct.start_container(config)


class TestHasHostAccessDanger:
    def test_safe_mounts(self, tmp_path) -> None:
        safe_dir = tmp_path / "shared"
        safe_dir.mkdir()
        mounts = [(safe_dir, "/data")]
        assert has_host_access_danger(mounts) is False

    def test_ssh_mount_dangerous(self, tmp_path, monkeypatch) -> None:
        home = tmp_path / "home"
        home.mkdir()
        ssh = home / ".ssh"
        ssh.mkdir()
        monkeypatch.setattr(ct.Path, "home", classmethod(lambda cls: home))
        mounts = [(ssh, "/root/.ssh")]
        assert has_host_access_danger(mounts) is True

    def test_etc_mount_dangerous(self) -> None:
        mounts = [(Path("/etc"), "/etc")]
        assert has_host_access_danger(mounts) is True

    def test_empty_mounts(self) -> None:
        assert has_host_access_danger([]) is False


class TestCleanupInactiveContainers:
    def test_returns_int(self) -> None:
        handles: dict[str, ContainerHandle] = {}
        # Without docker, returns 0 silently
        result = _cleanup_inactive_containers(handles)
        assert isinstance(result, int)


class TestContainerConfig:
    def test_defaults(self) -> None:
        cfg = ContainerConfig()
        assert cfg.image == "python:3.11-slim"
        assert cfg.timeout_seconds == 300
        assert cfg.mounts == []

    def test_with_mounts(self) -> None:
        cfg = ContainerConfig(
            mounts=[(Path("/data"), "/mnt/data")],
            env={"FOO": "bar"},
        )
        assert cfg.mounts == [(Path("/data"), "/mnt/data")]
        assert cfg.env["FOO"] == "bar"


class TestBackendConstants:
    def test_constants(self) -> None:
        assert BACKEND_AUTO == "auto"
        assert BACKEND_DOCKER == "docker"
        assert BACKEND_NONE == "none"