"""Configuration and secret handling for eaccode.

Storage layer for Phase A2: config.yaml location, defaults, YAML load/save,
secret masking and .env support. Paths are built manually instead of via
platformdirs (it doubles the app name on Windows).
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

import yaml

APP_DIR_NAME = "eaccode"
CONFIG_FILE_NAME = "config.yaml"

SECRET_KEY_SEGMENTS = ("api_key", "apikey", "secret", "token", "password")


class ConfigError(Exception):
    """Raised for any configuration problem (missing file, bad YAML, ...)."""


def config_dir() -> Path:
    """Return the platform-specific config directory (built manually)."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / APP_DIR_NAME
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_DIR_NAME


def data_dir() -> Path:
    """Return the platform-specific data directory (sessions, skills, ...)."""
    if os.name == "nt":
        return config_dir()
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


def config_path() -> Path:
    """Absolute path of the config file."""
    return config_dir() / CONFIG_FILE_NAME


def defaults() -> dict[str, Any]:
    """Fresh default configuration structure."""
    return {
        "model": {"default": "", "fallback": []},
        "providers": {},
        "paths": {"data": str(data_dir())},
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override into base (recursive for nested mappings)."""
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config merged over defaults. Raises ConfigError on missing/bad file."""
    target = path or config_path()
    if not target.exists():
        raise ConfigError(f"no config found at {target} - run 'config init' first")
    try:
        with target.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {target}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"invalid config structure in {target}: expected a mapping")
    return _deep_merge(defaults(), raw)


def save_config(cfg: dict[str, Any], path: Path | None = None) -> Path:
    """Write config with restricted permissions; returns the written path."""
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False, allow_unicode=True)
    with contextlib.suppress(OSError):
        os.chmod(target, 0o600)  # Windows: chmod is best effort only
    return target


def ensure_config(path: Path | None = None) -> Path:
    """Create config with defaults if missing; returns the config path."""
    target = path or config_path()
    if not target.exists():
        save_config(defaults(), target)
    return target


def load_env() -> None:
    """Load .env files (config dir + current directory) into os.environ."""
    from dotenv import load_dotenv

    for dotenv_path in (config_dir() / ".env", Path.cwd() / ".env"):
        load_dotenv(dotenv_path=dotenv_path, override=False)


def mask_secret(value: Any) -> str:
    """Mask a secret for display: keep at most the first 3 characters."""
    if not isinstance(value, str) or not value:
        return "***"
    if len(value) <= 6:
        return "***"
    return f"{value[:3]}***"


def is_secret_key(key: str) -> bool:
    """True if a dotted key path points at a secret value.

    Segment-based so that e.g. ``api_key`` matches but ``api_key_env``
    (the name of an environment variable, not a secret) does not.
    """
    parts = key.lower().replace("-", "_").split(".")
    return any(part in SECRET_KEY_SEGMENTS for part in parts)


def get_value(conf: dict[str, Any], dotted_key: str) -> Any:
    """Read a value by dotted path. Raises ConfigError for unknown keys."""
    node: Any = conf
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise ConfigError(f"unknown config key: {dotted_key}")
        node = node[part]
    return node


def _coerce(value: str, current: Any) -> Any:
    """Coerce a CLI string into the type of the current value (lists, ...)."""
    if isinstance(current, list):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def set_value(conf: dict[str, Any], dotted_key: str, value: Any) -> None:
    """Set a value by dotted path. Raises ConfigError for unknown keys.

    Missing intermediate sections are auto-created inside the dynamic
    ``providers`` tree (e.g. ``providers.openrouter.api_key``); all other
    sections stay strict.
    """
    if not dotted_key:
        raise ConfigError("empty config key")
    parts = dotted_key.split(".")
    node: Any = conf
    for index, part in enumerate(parts[:-1]):
        child = node.get(part)
        if not isinstance(child, dict):
            if parts[0] == "providers" and index > 0 and child is None:
                child = {}
                node[part] = child
            else:
                raise ConfigError(f"unknown config section: {dotted_key}")
        node = child
    final = parts[-1]
    if final not in node and not (parts[0] == "providers" and len(parts) > 1):
        raise ConfigError(f"unknown config key: {dotted_key}")
    node[final] = _coerce(value, node.get(final))


def delete_value(conf: dict[str, Any], dotted_key: str) -> None:
    """Remove a value by dotted path. Raises ConfigError for unknown keys."""
    parts = dotted_key.split(".")
    node: Any = conf
    for part in parts[:-1]:
        if not isinstance(node.get(part), dict):
            raise ConfigError(f"unknown config section: {dotted_key}")
        node = node[part]
    final = parts[-1]
    if final not in node:
        raise ConfigError(f"unknown config key: {dotted_key}")
    del node[final]


def provider_key_status(provider: dict[str, Any] | None) -> str:
    """Describe the api key state: 'set (file)' / 'set (env: VAR)' / 'not set'."""
    provider = provider or {}
    env_var = provider.get("api_key_env")
    if env_var and os.environ.get(env_var):
        return f"set (env: {env_var})"
    if provider.get("api_key"):
        return "set (file)"
    return "not set"
