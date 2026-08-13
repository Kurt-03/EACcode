"""config subcommands, shared by the CLI and the interactive REPL."""

from __future__ import annotations

import getpass
import sys
from typing import Any, TextIO

from eaccode import config as cfg

USAGE = """\
Usage: config <command> [args]

Commands:
  init               create config.yaml with defaults
  path               show the config file path
  show               show config values (secrets masked)
  get <key>          show one value (secrets refused)
  set <key> <value>  set a value (comma-separated -> list)
  set-key <key>      store a secret via hidden prompt
  unset <key>        remove a value
"""


def _fmt(value: Any) -> str:
    """Format a config value for display."""
    if value is None or value == "":
        return "(unset)"
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    if isinstance(value, dict):
        return "<mapping - use 'config show'>"
    return str(value)


def _dump_section(lines: list[str], value: Any, indent: str) -> None:
    """Dump a config subtree, masking anything that looks like a secret."""
    if isinstance(value, dict):
        for key, item in value.items():
            if cfg.is_secret_key(key) and item:
                lines.append(f"{indent}{key}: {cfg.mask_secret(item)}")
            else:
                _dump_section(lines, item, f"{indent}{key}.")
    else:
        lines.append(f"{indent.rstrip('.')}: {_fmt(value)}")


def _cmd_init(stdout: TextIO) -> int:
    path = cfg.config_path()
    if path.exists():
        stdout.write(f"config already exists at {path}\n")
        return 0
    cfg.save_config(cfg.defaults(), path)
    stdout.write(f"config.yaml created at {path}\n")
    return 0


def _cmd_show(stdout: TextIO) -> int:
    conf = cfg.load_config()
    lines: list[str] = []
    for section, value in conf.items():
        if section == "providers":
            lines.append("providers:")
            for name, provider in (value or {}).items():
                provider = provider or {}
                lines.append(f"  {name}:")
                status = cfg.provider_key_status(provider)
                if provider.get("api_key"):
                    lines.append(f"    api_key: {status} [{cfg.mask_secret(provider['api_key'])}]")
                else:
                    lines.append(f"    api_key: {status}")
        else:
            _dump_section(lines, value, f"{section}.")
    stdout.write("\n".join(lines) + "\n")
    return 0


def _cmd_get(rest: list[str], stdout: TextIO) -> int:
    if len(rest) != 1:
        stdout.write("Usage: config get <key>\n")
        return 1
    key = rest[0]
    if cfg.is_secret_key(key):
        stdout.write("Error: refusing to show a secret - use 'config show' for status\n")
        return 1
    value = cfg.get_value(cfg.load_config(), key)
    if isinstance(value, dict):
        stdout.write("Error: that key is a section - use 'config show'\n")
        return 1
    stdout.write(f"{_fmt(value)}\n")
    return 0


def _cmd_set(rest: list[str], stdout: TextIO) -> int:
    if len(rest) < 2:
        stdout.write("Usage: config set <key> <value>\n")
        return 1
    key, value = rest[0], " ".join(rest[1:])
    conf = cfg.load_config()
    cfg.set_value(conf, key, value)
    cfg.save_config(conf)
    stdout.write("ok\n")
    return 0


def _cmd_set_key(rest: list[str], stdout: TextIO) -> int:
    if len(rest) != 1:
        stdout.write("Usage: config set-key <key>\n")
        return 1
    key = rest[0]
    if not cfg.is_secret_key(key):
        stdout.write(f"Error: {key} does not look like a secret key\n")
        return 1
    secret = getpass.getpass("Enter secret (hidden): ", stream=stdout)
    if not secret:
        stdout.write("Error: empty secret, nothing stored\n")
        return 1
    conf = cfg.load_config()
    cfg.set_value(conf, key, secret)
    path = cfg.save_config(conf)
    stdout.write(f"secret stored in {path} (restricted permissions)\n")
    return 0


def _cmd_unset(rest: list[str], stdout: TextIO) -> int:
    if len(rest) != 1:
        stdout.write("Usage: config unset <key>\n")
        return 1
    key = rest[0]
    conf = cfg.load_config()
    cfg.delete_value(conf, key)
    cfg.save_config(conf)
    stdout.write("ok\n")
    return 0


def run_config_command(
    args: list[str],
    stdout: TextIO | None = None,
    stdin: TextIO | None = None,
) -> int:
    """Dispatch a config subcommand; returns an exit code (0 = ok)."""
    del stdin  # reserved: hidden input for set-key arrives via getpass
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(USAGE)
        return 0
    command, rest = args[0], args[1:]
    try:
        if command == "init":
            return _cmd_init(stdout)
        if command == "path":
            stdout.write(f"{cfg.config_path()}\n")
            return 0
        if command == "show":
            return _cmd_show(stdout)
        if command == "get":
            return _cmd_get(rest, stdout)
        if command == "set":
            return _cmd_set(rest, stdout)
        if command == "set-key":
            return _cmd_set_key(rest, stdout)
        if command == "unset":
            return _cmd_unset(rest, stdout)
        stdout.write(f"Unknown config command: {command}\n\n{USAGE}")
        return 1
    except cfg.ConfigError as exc:
        stdout.write(f"Error: {exc}\n")
        return 1
