"""Echtes Tirith-Binary-Wrapper (Phase 3, H1).

Tirith ist ein externes Security-Scanner Binary (sheeki03/tirith auf GitHub)
das mit Cosign/SHA-256 verifizierbar ist. eaccode lädt es beim ersten
Bedarf automatisch herunter und cached es in `~/.local/share/eaccode/bin/`.

Output-Format (Tirith v0.3.3):

    JSON {"action": "allow|warn|block",
         "findings": [{"severity": "HIGH|MEDIUM|LOW", "title", "description", "remediation_hint"}],
         "summary": "..."}

Bei fehlender Binary oder Netzwerkfehler: fail-Open (`action: "allow"`)
falls `security.tirith_fail_open` True ist (Default); sonst synthetisches
``warn`` mit Finding ``tirith-install-error``.

08-18: Phase 3, Plan D.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


REPO = "sheeki03/tirith"
TARGET_VERSION = "v0.3.3"
INSTALL_DIR_RELATIVE = "bin"


def _platform_target() -> str:
    """Return the archive filename appropriate for this OS+arch."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows" and machine in ("amd64", "x86_64"):
        return "tirith-x86_64-pc-windows-msvc.zip"
    if system == "darwin":
        if machine == "arm64":
            return "tirith-aarch64-apple-darwin.tar.gz"
        return "tirith-x86_64-apple-darwin.tar.gz"
    # Linux
    if machine == "aarch64":
        return "tirith-aarch64-unknown-linux-gnu.tar.gz"
    return "tirith-x86_64-unknown-linux-gnu.tar.gz"


def _install_path() -> Path:
    """Where the eaccode-side tirith binary lives."""
    from eaccode import config as cfg

    try:
        bin_dir = cfg.data_dir() / "bin"
    except Exception:
        bin_dir = Path.home() / ".local" / "share" / "eaccode" / "bin"
    return bin_dir / ("tirith.exe" if os.name == "nt" else "tirith")


def _download_archive(target: str) -> tuple[bytes | None, str]:
    """Download ``tirith-<target>`` archive; return (bytes, error)."""
    import urllib.error
    import urllib.request

    url = (
        f"https://github.com/{REPO}/releases/download/"
        f"{TARGET_VERSION}/tirith-{target}"
    )
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
        return data, ""
    except urllib.error.URLError as exc:
        return None, f"download failed: {exc}"


def _download_checksums() -> str | None:
    """Download checksums.txt for SHA-256 verification."""
    import urllib.error
    import urllib.request

    url = (
        f"https://github.com/{REPO}/releases/download/"
        f"{TARGET_VERSION}/checksums.txt"
    )
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError:
        return None


def _verify_sha256(data: bytes, target: str, checksums_text: str | None) -> bool:
    """Verify data against checksums.txt entry for ``target``."""
    import hashlib

    if not checksums_text:
        # Hermes-Verbatim: downloads proceed only when SHA-256 verified;
        # without checksums we cannot verify and return False.
        return False
    expected_hash = None
    for line in checksums_text.splitlines():
        # Format: "<hash>  <filename>"
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1].endswith(target):
            expected_hash = parts[0]
            break
    if not expected_hash:
        return False
    actual_hash = hashlib.sha256(data).hexdigest()
    return actual_hash == expected_hash


def _extract_and_install(target: str, archive_data: bytes) -> bool:
    """Extract archive and place ``tirith`` at ``_install_path()``."""
    import io
    import tarfile
    import zipfile

    install = _install_path()
    install.parent.mkdir(parents=True, exist_ok=True)

    if target.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive_data)) as zf:
            for entry in zf.namelist():
                if entry.endswith(("tirith", "tirith.exe")):
                    with zf.open(entry) as src, open(install, "wb") as dest:
                        dest.write(src.read())
                    break
    else:
        with tarfile.open(fileobj=io.BytesIO(archive_data), mode="r:gz") as tf:
            for member in tf.getmembers():
                if member.isfile() and member.name.endswith(("/tirith", "\\tirith")):
                    with tf.extractfile(member) as src, open(install, "wb") as dest:
                        dest.write(src.read())
                    break

    if not install.exists():
        return False

    # POSIX: ensure executable
    if os.name != "nt":
        install.chmod(0o755)
    return True


def _install(*, log_failures: bool = True) -> tuple[Path | None, str]:
    """Download + verify + install tirith. Returns (path, error)."""
    target = _platform_target()
    data, err = _download_archive(target)
    if not data:
        return None, err

    checksums = _download_checksums()
    if not _verify_sha256(data, target, checksums):
        return None, "SHA-256 verification failed (or no checksums)"

    if not _extract_and_install(target, data):
        return None, "extraction failed"

    return _install_path(), ""


def _tirith_lock() -> threading.Lock:
    """Module-level install lock (Hermes-Verbatim)."""
    global _lock
    if not hasattr(_tirith_lock, "_lock"):
        _tirith_lock._lock = threading.Lock()  # type: ignore[attr-defined]
    return _tirith_lock._lock  # type: ignore[attr-defined]


_lock: threading.Lock | None = None


_INSTALL_RETRIES = 1
_INSTALL_BACKOFF_SECONDS = 1.0


def ensure_installed(*, log_failures: bool = True) -> tuple[Path | None, str]:
    """Ensure tirith is installed, installing if needed.

    Threadsafe via module-level lock. Returns (path, error).

    A 0-byte install path (silent extraction failure) is treated as
    "not installed" and re-attempted.
    """
    path = _install_path()
    if path.exists() and path.stat().st_size > 1024:
        # 1KB minimum — a real tirith.exe is ~9MB. Anything less means
        # previous extraction failed silently.
        return path, ""

    lock = _tirith_lock()
    with lock:
        # Re-check after acquiring lock
        path = _install_path()
        if path.exists() and path.stat().st_size > 1024:
            return path, ""
        # Clean up any stale empty file before retry
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass

        last_err = ""
        for _ in range(_INSTALL_RETRIES + 1):
            path, err = _install(log_failures=log_failures)
            if path and path.exists() and path.stat().st_size > 1024:
                return path, ""
            last_err = err
            time.sleep(_INSTALL_BACKOFF_SECONDS)
        return None, last_err


def check_command_security(command: str) -> dict[str, Any]:
    """Run tirith ``check --format=json`` and return parsed result.

    Falls back to ``{"action": "allow", "findings": [], ...}`` on any
    error, configured by ``security.tirith_fail_open``. Fail-closed
    (warn) when explicitly opted into.
    """
    fail_open = _tirith_fail_open_setting()
    path, err = ensure_installed()
    if not path or not Path(path).exists():
        if fail_open:
            return {"action": "allow", "findings": [], "summary": "tirith unavailable"}
        return _tirith_import_error_result(err or "tirith binary not found")
    try:
        proc = subprocess.run(
            [str(path), "check", "--format=json", command],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode not in (0, 1):
            if fail_open:
                return {
                    "action": "allow",
                    "findings": [],
                    "summary": f"tirith failed (rc={proc.returncode})",
                }
            return _tirith_import_error_result(proc.stderr.strip())
        result = json.loads(proc.stdout)
        if not isinstance(result, dict):
            return {"action": "allow", "findings": [], "summary": "tirith bad shape"}
        return result
    except subprocess.TimeoutExpired:
        return {"action": "allow", "findings": [], "summary": "tirith timeout"}
    except Exception as exc:
        if fail_open:
            return {"action": "allow", "findings": [], "summary": f"tirith error: {exc}"}
        return _tirith_import_error_result(str(exc))


def _tirith_fail_open_setting() -> bool:
    """Read security.tirith_fail_open from config; default True."""
    try:
        from eaccode import config as cfg

        sec = (cfg.load_config() or {}).get("security", {}) or {}
        return bool(sec.get("tirith_fail_open", True))
    except Exception:
        return True


def _tirith_import_error_result(reason: str) -> dict[str, Any]:
    """Synthesize a fail-closed warning finding (Hermes-Verbatim)."""
    return {
        "action": "warn",
        "findings": [
            {
                "rule_id": "tirith-install-error",
                "severity": "HIGH",
                "title": "Tirith security scanner unavailable",
                "description": (
                    f"The Tirith security scanner could not be loaded: {reason}. "
                    "Because security.tirith_fail_open is False, this command "
                    "cannot be silently allowed."
                ),
            }
        ],
        "summary": "Tirith unavailable (fail-closed)",
    }


def get_installed_path() -> Path:
    """Public accessor for the install path (used by tests, README)."""
    return _install_path()
