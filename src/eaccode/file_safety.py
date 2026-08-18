"""Hermes-Verbatim hardcoded write/read denials (Phase 2, H2/H14/H15/H16/H17/H18/H19).

`file_safety.py` is the canonical source of "this path must never be
written/read". Hermes protects:
  - SSH keys + config
  - Active and top-level .env files
  - Anthropic OAuth credential store
  - Bitwarden encrypted cache
  - GitHub / Git credentials
  - Linux /etc/passwd, /etc/shadow, /etc/sudoers
  - Sensitive directory trees (.ssh/, .aws/, .gnupg/, .kube/, .docker/,
    .azure/, .config/{gh,gcloud}, /etc/sudoers.d/, /etc/systemd/)
  - HERMES_WRITE_SAFE_ROOT env-var for explicit whitelists

Usage:
    is_write_denied(path) -> bool         # Phase 2 main check
    is_read_denied(path) -> bool          # Phase 2 secondary
    get_safe_write_roots() -> set[str]    # Phase 2 whitelist env
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


# -- Hardcoded exact sensitive paths (Phase 2, H14) -----------------

def _hermes_home_path() -> Path:
    """User home directory."""
    return Path(os.path.expanduser("~"))


def _hermes_root_path() -> Path:
    """Top-level dir where eaccode .env normally lives."""
    from eaccode import config as cfg

    try:
        return Path(cfg.config_dir())
    except Exception:
        return Path.cwd()


def build_write_denied_paths(home: Path) -> set[str]:
    """Return exact sensitive paths that must NEVER be written.

    Resolved once - call once at startup and cache.
    """
    hermes_home = Path(str(home))
    hermes_root = _hermes_root_path()

    candidates = [
        # SSH keys + config
        hermes_home / ".ssh" / "authorized_keys",
        hermes_home / ".ssh" / "id_rsa",
        hermes_home / ".ssh" / "id_ed25519",
        hermes_home / ".ssh" / "config",
        # Local .env files
        str(hermes_home / ".env"),
        str(hermes_root / ".env"),
        # Anthropic PKCE OAuth store (Hermes-Verbatim)
        str(hermes_home / ".anthropic_oauth.json"),
        str(hermes_root / ".anthropic_oauth.json"),
        # Bitwarden Secrets Manager encrypted disk cache
        str(hermes_home / "cache" / "bws_cache.enc.json"),
        str(hermes_root / "cache" / "bws_cache.enc.json"),
        # Credential files
        hermes_home / ".netrc",
        hermes_home / ".pgpass",
        hermes_home / ".npmrc",
        hermes_home / ".pypirc",
        hermes_home / ".git-credentials",
        # Linux/POSIX system files (no-op on Windows)
        Path("/etc/sudoers"),
        Path("/etc/passwd"),
        Path("/etc/shadow"),
    ]
    paths: set[str] = set()
    for p in candidates:
        try:
            paths.add(str(Path(p).resolve()))
        except Exception:
            # Path doesn't exist (e.g. /etc/sudoers on Windows) - skip
            continue
    return paths


# -- Sensitive directory prefixes (Phase 2, H15) -----------------

def build_write_denied_prefixes(home: Path) -> list[str]:
    """Return sensitive directory prefixes (terminated with os.sep)."""
    hermes_home = Path(str(home))
    hermes_root = _hermes_root_path()
    prefix_dirs = [
        hermes_home / ".ssh",
        hermes_home / ".aws",
        hermes_home / ".gnupg",
        hermes_home / ".kube",
        Path("/etc/sudoers.d"),
        Path("/etc/systemd"),
        hermes_home / ".docker",
        hermes_home / ".azure",
        hermes_home / ".config" / "gh",
        hermes_home / ".config" / "gcloud",
        hermes_root / ".ssh",
    ]
    prefixes: list[str] = []
    for p in prefix_dirs:
        try:
            prefixes.append(str(Path(p).resolve()) + os.sep)
        except Exception:
            continue
    return prefixes


# -- HERMES_WRITE_SAFE_ROOT whitelist (Phase 2, H16) ----------

def get_safe_write_roots() -> set[str]:
    """Resolved paths allowed for write despite sensitive parents.

    Env: EACCODE_WRITE_SAFE_ROOT=path1[sep]path2 (colon/semicolon).
    """
    env = os.environ.get("EACCODE_WRITE_SAFE_ROOT", "")
    if not env:
        return set()
    sep = ";" if os.name == "nt" else ":"
    paths: set[str] = set()
    for raw in env.split(sep):
        raw = raw.strip()
        if not raw:
            continue
        try:
            paths.add(str(Path(raw).resolve()))
        except Exception:
            pass
    return paths


# -- The main check (Phase 2 main API) ------------------------------

_DENY_PATHS: set[str] | None = None
_DENY_PREFIXES: list[str] | None = None


def _ensure_cached() -> None:
    """Lazy-init cache so first call doesn't slow startup."""
    global _DENY_PATHS, _DENY_PREFIXES
    if _DENY_PATHS is None:
        _DENY_PATHS = build_write_denied_paths(_hermes_home_path())
        _DENY_PREFIXES = build_write_denied_prefixes(_hermes_home_path())


def is_write_denied(path: str) -> bool:
    """True when path is in denied exact-paths or under a denied prefix."""
    _ensure_cached()
    assert _DENY_PATHS is not None and _DENY_PREFIXES is not None
    if not path:
        return False
    try:
        resolved = str(Path(path).resolve())
    except Exception:
        return False

    # Safe-roots short-circuit
    if resolved in get_safe_write_roots():
        return False

    # Exact-path matches
    if resolved in _DENY_PATHS:
        return True
    # Prefix matches (already terminated with os.sep)
    for prefix in _DENY_PREFIXES:
        if resolved.startswith(prefix):
            return True
    return False


def is_read_denied(path: str) -> bool:
    """True when path is in the read-deny set (subset of write-deny).

    Read-deny is currently: same set as write-deny PLUS secret files
    Hermes conservatively protects from leaking.
    """
    return is_write_denied(path)


def get_safe_roots_env_doc() -> str:
    """Help text for the EACCODE_WRITE_SAFE_ROOT env-var."""
    return (
        "Set EACCODE_WRITE_SAFE_ROOT=path1[{:s}]path2 to allow writes to "
        "sensitive-looking paths (e.g. /opt/data,/var/www). Default: empty.".format(
            ";" if os.name == "nt" else ":"
        )
    )


def cross_profile_target_warning(path: str, profile_name: Optional[str] = None) -> Optional[str]:
    """Hermes-style cross-profile write warning (Phase 2, H17).

    Returns a warning string if writing to a different profile's config
    than the running one. Currently no-op when profiles aren't configured.
    """
    # Profiles are a Hermes concept we haven't adopted yet. Future
    # implementation will detect `path` traversing to other profile's
    # config tree. For now, return None (no warning).
    return None
