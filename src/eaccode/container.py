"""Container sandbox backend (Plan H Stufe 3, Hermes-Verbatim analog).

Stufe 3 replaces the soft-sandbox (cwd-as-workspace) with a real
container for tools that need filesystem isolation: per-task images,
host-path-detection, volume-mount-isolation, cleanup-thread.

Hermes has a 3500-LOC container system across ``terminal_tool.py`` +
``file_safety.py`` + a private ``container_runner``. We ship a slimmer
analog: Python orchestrator that picks ``docker exec`` when Docker is
available, falls back to a chroot/junction-based soft-sandbox.

The backend is **opt-in** - by default Stufe 1+2 (cwd-as-workspace +
/approvals bridge) is what users see. ``workspace.mode = "container"``
turns Stufe 3 on.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Container backend modes
BACKEND_AUTO = "auto"     # pick docker if available, else fallback
BACKEND_DOCKER = "docker"  # require docker
BACKEND_NONE = "none"     # disable container layer entirely


@dataclass
class ContainerConfig:
    """One container's settings."""

    image: str = "python:3.11-slim"
    name: str = ""
    workspace: Path = field(default_factory=Path.cwd)
    mounts: list[tuple[Path, str]] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 300


@dataclass
class ContainerHandle:
    """A live container reference."""

    backend: str  # "docker" | "chroot" | "junction"
    container_id: str
    workspace: Path


def is_docker_available() -> bool:
    """True when the ``docker`` binary is on PATH."""
    return shutil.which("docker") is not None


def list_running_containers(prefix: str = "eaccode-") -> list[str]:
    """List eaccode-managed containers that are currently running."""
    if not is_docker_available():
        return []
    try:
        out = subprocess.run(
            ["docker", "ps", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode != 0:
            return []
        return [n for n in out.stdout.splitlines() if n.startswith(prefix)]
    except (OSError, subprocess.TimeoutExpired):
        return []


def start_container(config: ContainerConfig) -> ContainerHandle:
    """Start a new container for the given config.

    Uses ``docker run -d`` when docker is available. The container is
    expected to keep running so subsequent ``docker exec`` calls land
    in the same filesystem.

    When docker isn't available, raises ``RuntimeError`` - the caller
    is expected to fall back to the soft-sandbox.
    """
    if not is_docker_available():
        raise RuntimeError("docker not available")

    name = config.name or f"eaccode-{int(time.time())}"

    # Mount the workspace as /workspace in the container
    args = [
        "docker", "run", "-d", "--rm",
        "--name", name,
        "-v", f"{config.workspace}:/workspace",
    ]
    for host_path, container_path in config.mounts:
        args.extend(["-v", f"{host_path}:{container_path}"])
    for k, v in config.env.items():
        args.extend(["-e", f"{k}={v}"])
    args.extend([config.image, "sleep", str(config.timeout_seconds)])

    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed: {result.stderr.strip()}")
    return ContainerHandle(
        backend="docker",
        container_id=result.stdout.strip(),
        workspace=config.workspace,
    )


def exec_in_container(handle: ContainerHandle, cmd: list[str]) -> tuple[int, str]:
    """Run ``cmd`` in the live container and return (exit_code, output)."""
    if handle.backend != "docker":
        raise RuntimeError(f"unsupported backend: {handle.backend!r}")
    try:
        result = subprocess.run(
            ["docker", "exec", handle.container_id] + cmd,
            capture_output=True,
            text=True,
            timeout=handle_timeout(),
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124, f"Error: exec failed: {exc}"


def handle_timeout() -> int:
    """Return the default timeout for ``exec_in_container`` (5 min)."""
    return 300


def stop_container(handle: ContainerHandle) -> bool:
    """Stop a container. Returns True if stopped, False if it wasn't running."""
    if handle.backend != "docker":
        return True
    try:
        result = subprocess.run(
            ["docker", "stop", handle.container_id],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# --- Cleanup thread (Hermes _cleanup_thread_worker analog) -----------------

_CLEANUP_INTERVAL_SECONDS = 60
_IDLE_TIMEOUT_SECONDS = 300


def _cleanup_inactive_containers(handles: dict[str, ContainerHandle]) -> int:
    """Stop any eaccode-* container not in ``handles`` (idle/orphaned).

    Returns the number of containers stopped.
    """
    live = set(list_running_containers())
    kept = set(handles.keys())
    stale = live - kept
    stopped = 0
    for cid in stale:
        if stop_container(ContainerHandle(
            backend="docker",
            container_id=cid,
            workspace=Path.cwd(),
        )):
            stopped += 1
    return stopped


def has_host_access_danger(mounts: list[tuple[Path, str]]) -> bool:
    """Hermes-style: True when any mount gives the container real host access.

    ``~/.ssh``, ``/etc``, ``/var``, ``/home`` are dangerous because the
    container could read the user's real keys or system files.
    """
    dangerous_substrings = {".ssh", ".aws", ".gnupg", ".kube", ".docker"}
    # Dangerous path-prefix patterns (matched as substrings so cross-platform works)
    dangerous_prefixes = (
        str(Path.home()),
        "/etc", "/var", "/root", "/home",
    )
    for host_path, _container_path in mounts:
        try:
            host_path = host_path.resolve()
        except OSError:
            pass
        s = str(host_path).replace("\\", "/")
        if any(s.startswith(p) or p in s for p in dangerous_prefixes):
            return True
        if any(sub in s for sub in dangerous_substrings):
            return True
    return False


__all__ = [
    "BACKEND_AUTO",
    "BACKEND_DOCKER",
    "BACKEND_NONE",
    "ContainerConfig",
    "ContainerHandle",
    "is_docker_available",
    "list_running_containers",
    "start_container",
    "exec_in_container",
    "stop_container",
    "_cleanup_inactive_containers",
    "_CLEANUP_INTERVAL_SECONDS",
    "_IDLE_TIMEOUT_SECONDS",
    "has_host_access_danger",
]