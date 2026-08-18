"""Environment probe (Phase G.6, Plan G v5).

Detects which tools the local environment exposes (Python version, pip,
PEP 668, git, npm, cargo, docker, etc.) so the model can be told up
front what is available.

Mirrors Hermes' tools/env_probe.py:get_environment_probe_line. The
probe is cached for the process lifetime; tests can force a re-probe.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from pathlib import Path


_GEN = 0
_LOCK = threading.Lock()
_CACHE: dict[str, str | None] = {}
_PROBE_THREAD: threading.Thread | None = None


def _bump() -> int:
    global _GEN
    _GEN += 1
    return _GEN


def _probe_python_version() -> str | None:
    try:
        result = subprocess.run(
            [sys.executable, "--version"],
            capture_output=True, text=True, timeout=3,
        )
        for stream in (result.stdout, result.stderr):
            if stream:
                return stream.strip()
    except Exception:
        return None
    return None


def _probe_pip() -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=3,
        )
        return result.returncode == 0
    except Exception:
        return False


def _probe_pep668() -> bool:
    """Detect PEP 668 (externally-managed-environment)."""
    if sys.platform != "linux":
        return False
    candidates = [
        Path("/usr/lib/python3/dist-packages/EXTERNALLY-MANAGED"),
        Path("/usr/lib/python3.12/EXTERNALLY-MANAGED"),
    ]
    for path in candidates:
        if path.exists():
            return True
    try:
        import sysconfig

        stdlib = Path(sysconfig.get_paths().get("stdlib", ""))
        return (stdlib / "EXTERNALLY-MANAGED").exists()
    except Exception:
        return False


def _probe_binary(name: str) -> bool:
    return shutil.which(name) is not None


def _probe_all() -> dict[str, str | None]:
    return {
        "python": _probe_python_version(),
        "pip": "yes" if _probe_pip() else "no",
        "pep668": "yes" if _probe_pep668() else "no",
        "git": "yes" if _probe_binary("git") else "no",
        "npm": "yes" if _probe_binary("npm") else "no",
        "cargo": "yes" if _probe_binary("cargo") else "no",
        "docker": "yes" if _probe_binary("docker") else "no",
        "pytest": "yes" if _probe_binary("pytest") else "no",
    }


def _build_probe_line(data: dict[str, str | None]) -> str:
    parts: list[str] = []
    py = data.get("python")
    if py:
        parts.append(f"Python: {py}")
    pip = data.get("pip")
    if pip == "yes":
        parts.append("pip: available")
    pep = data.get("pep668")
    if pep == "yes":
        parts.append("PEP 668: active (use --break-system-packages or venv)")
    for tool in ("git", "npm", "cargo", "docker", "pytest"):
        if data.get(tool) == "yes":
            parts.append(f"{tool}: available")
    if not parts:
        return "Environment probe: (no information available)"
    return "Environment probe: " + " | ".join(parts)


def get_environment_probe_line(*, force_refresh: bool = False) -> str:
    """Return the cached environment probe line. Refreshes lazily."""
    if not _CACHE or force_refresh:
        with _LOCK:
            if not _CACHE or force_refresh:
                _bump()
                _CACHE.clear()
                _CACHE.update({k: v for k, v in _probe_all().items()})
                _CACHE["_line"] = _build_probe_line(_CACHE)
    return _CACHE["_line"]  # type: ignore[return-value]


def get_environment_data(*, force_refresh: bool = False) -> dict[str, str | None]:
    """Return the raw probe dict (for tests / advanced callers)."""
    if not _CACHE or force_refresh:
        get_environment_probe_line(force_refresh=force_refresh)
    return {k: v for k, v in _CACHE.items() if k != "_line"}


def _reset_cache_for_tests() -> None:
    """Drop the cached probe so the next call re-runs the subprocesses."""
    with _LOCK:
        _bump()
        _CACHE.clear()


def warm_environment_probe_async() -> None:
    """Start a background probe worker. Idempotent."""
    global _PROBE_THREAD
    with _LOCK:
        if _PROBE_THREAD is not None and _PROBE_THREAD.is_alive():
            return
        _PROBE_THREAD = threading.Thread(
            target=_probe_worker,
            args=(_GEN,),
            name="env-probe",
            daemon=True,
        )
        _PROBE_THREAD.start()


def _probe_worker(gen: int) -> None:
    try:
        get_environment_probe_line()
    except Exception:
        pass
    _ = gen  # marker for future cache-invalidation generations


__all__ = [
    "get_environment_probe_line",
    "get_environment_data",
    "warm_environment_probe_async",
    "_reset_cache_for_tests",
]
