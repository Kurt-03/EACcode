"""config subcommands, shared by the CLI and the interactive REPL."""

from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from eaccode import config as cfg
from eaccode import cron, memory, permissions, router, skills, store

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

PROVIDER_USAGE = """\
Usage: provider <command> [args]

Commands:
  list                            show providers with key status
  add <name> [--base-url URL]     register a provider
      [--api-key-env VAR]         ... key comes from this env variable
  remove <name>                   unregister a provider
  set-key <name>                  store the api key via hidden prompt
"""

MODEL_USAGE = """\
Usage: model <command> [args]

Commands:
  list                           show the model catalog with default/fallback
  add <provider/model>           register a custom model (e.g. ollama/deepseek-r1)
      [--base-url URL]           ... set the provider base url (local servers)
  set-default <provider/model>   set the default model
  set-fallback <m1,m2,...>       set the fallback chain
  ping <provider/model>          send a live test call (expects 'pong')
"""


def parse_args(text: str) -> list[str]:
    """Split command text into arguments, honoring single/double quotes.

    Backslashes are NOT escapes (Windows paths stay intact). Unterminated
    quotes raise ValueError.
    """
    args: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in text.strip():
        if quote is not None:
            if char == quote:
                quote = None
            else:
                current.append(char)
        elif char in ("'", '"'):
            quote = char
        elif char.isspace():
            if current:
                args.append("".join(current))
                current = []
        else:
            current.append(char)
    if quote is not None:
        raise ValueError("unterminated quote in command")
    if current:
        args.append("".join(current))
    return args


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


HELP_TEXT = """\
Commands:
  /help           show this help
  /version        show eaccode version
  /clear          clear the screen and the chat history
  /config <cmd>   manage configuration (init, show, set, ...)
  /provider <cmd> manage providers (add, list, remove, set-key)
  /model <cmd>    manage models (list, set-default, ping, ...)
  /memory <cmd>   manage memory (add, show, remove, user add)
  /skill <cmd>    manage skills (list, view, new, remove)
  /session <cmd>  search past sessions (browse, search, show)
  /permissions    permission modes and rules (status, mode, allow, deny)
  /job <cmd>      scheduled jobs (list, add, remove, pause, resume, run)
  /mcp <cmd>      MCP servers (list, add, import, remove)
  /exit           leave eaccode (alias: /quit)

Everything else is sent to the agent as a chat message.
"""


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


# ---------------------------------------------------------------------------
# provider / model subcommands (Phase A3 - model router)
# ---------------------------------------------------------------------------


def _parse_flags(args: list[str], allowed: tuple[str, ...]) -> dict[str, str]:
    """Parse --flag value pairs; raises ValueError on unknown flags."""
    flags: dict[str, str] = {}
    index = 0
    while index < len(args):
        arg = args[index]
        if arg.startswith("--"):
            name = arg[2:].replace("-", "_")
            if name not in allowed:
                raise ValueError(f"unknown flag: {arg}")
            if index + 1 >= len(args):
                raise ValueError(f"missing value for {arg}")
            flags[name] = args[index + 1]
            index += 2
        else:
            raise ValueError(f"unexpected argument: {arg}")
    return flags


def _cmd_provider_list(stdout: TextIO) -> int:
    conf = cfg.load_config()
    names = sorted((conf.get("providers") or {}).keys())
    if not names:
        stdout.write("no providers configured - run 'provider add <name>'\n")
        return 0
    for name in names:
        provider = conf["providers"][name] or {}
        base = provider.get("base_url") or "-"
        stdout.write(f"{name:<16} key: {cfg.provider_key_status(provider):<28} base_url: {base}\n")
    return 0


def _cmd_provider_add(rest: list[str], stdout: TextIO) -> int:
    if not rest:
        stdout.write("Usage: provider add <name> [--base-url URL] [--api-key-env VAR]\n")
        return 1
    name = rest[0]
    try:
        flags = _parse_flags(rest[1:], ("base_url", "api_key_env"))
    except ValueError as exc:
        stdout.write(f"Error: {exc}\n")
        return 1
    conf = cfg.load_config()
    provider = conf.setdefault("providers", {}).setdefault(name, {})
    if flags.get("base_url"):
        provider["base_url"] = flags["base_url"]
    if flags.get("api_key_env"):
        provider["api_key_env"] = flags["api_key_env"]
    cfg.save_config(conf)
    stdout.write(f"provider '{name}' added\n")
    return 0


def _cmd_provider_remove(rest: list[str], stdout: TextIO) -> int:
    if len(rest) != 1:
        stdout.write("Usage: provider remove <name>\n")
        return 1
    name = rest[0]
    conf = cfg.load_config()
    providers = conf.get("providers") or {}
    if name not in providers:
        stdout.write(f"Error: unknown provider: {name}\n")
        return 1
    del providers[name]
    cfg.save_config(conf)
    stdout.write(f"provider '{name}' removed\n")
    return 0


def _cmd_provider_set_key(rest: list[str], stdout: TextIO) -> int:
    if len(rest) != 1:
        stdout.write("Usage: provider set-key <name>\n")
        return 1
    return _cmd_set_key([f"providers.{rest[0]}.api_key"], stdout)


def _cmd_model_list(stdout: TextIO) -> int:
    conf = cfg.load_config()
    model = conf.get("model") or {}
    stdout.write(f"default:  {model.get('default') or '(unset)'}\n")
    stdout.write(f"fallback: {_fmt(model.get('fallback') or [])}\n")
    known = router.all_model_ids(conf)
    if not known:
        stdout.write("no models known - run 'model set-default <provider/model>'\n")
        return 0
    stdout.write("catalog:\n")
    for model_id in known:
        marker = ""
        if model_id == model.get("default"):
            marker = " (default)"
        elif model_id in (model.get("fallback") or []):
            marker = " (fallback)"
        stdout.write(f"  - {model_id}{marker}\n")
    return 0


def _cmd_model_add(rest: list[str], stdout: TextIO) -> int:
    if not rest:
        stdout.write("Usage: model add <provider/model> [--base-url URL]\n")
        return 1
    model_id = rest[0]
    if "/" not in model_id:
        stdout.write("Error: model id must look like '<provider>/<model>'\n")
        return 1
    provider_name, model_name = model_id.split("/", 1)
    try:
        flags = _parse_flags(rest[1:], ("base_url",))
    except ValueError as exc:
        stdout.write(f"Error: {exc}\n")
        return 1
    conf = cfg.load_config()
    provider = conf.setdefault("providers", {}).setdefault(provider_name, {})
    if flags.get("base_url"):
        provider["base_url"] = flags["base_url"]
    models = provider.setdefault("models", [])
    if model_id not in models:
        models.append(model_id)
    cfg.save_config(conf)
    stdout.write(f"model '{model_id}' registered\n")
    return 0


def _cmd_model_set_default(rest: list[str], stdout: TextIO) -> int:
    if len(rest) != 1:
        stdout.write("Usage: model set-default <provider/model>\n")
        return 1
    conf = cfg.load_config()
    cfg.set_value(conf, "model.default", rest[0])
    cfg.save_config(conf)
    stdout.write(f"default model: {rest[0]}\n")
    return 0


def _cmd_model_set_fallback(rest: list[str], stdout: TextIO) -> int:
    if len(rest) != 1:
        stdout.write("Usage: model set-fallback <m1,m2,...>\n")
        return 1
    conf = cfg.load_config()
    cfg.set_value(conf, "model.fallback", rest[0])
    cfg.save_config(conf)
    stdout.write(f"fallback chain: {_fmt(conf['model']['fallback'])}\n")
    return 0


def _cmd_model_ping(rest: list[str], stdout: TextIO) -> int:
    if len(rest) != 1:
        stdout.write("Usage: model ping <provider/model>\n")
        return 1
    try:
        reply = router.ping_model(rest[0])
    except router.ModelError as exc:
        stdout.write(f"Error: {exc}\n")
        return 1
    stdout.write(f"{rest[0]} replied: {reply}\n")
    return 0


MEMORY_USAGE = """\
Usage: memory <command> [args]

Commands:
  show                 show MEMORY.md and USER.md
  add <text>           append a fact to MEMORY.md
  user add <text>      append a fact to USER.md
  remove <substring>   remove MEMORY.md entries containing substring
"""


def run_memory_command(args: list[str], stdout: TextIO | None = None) -> int:
    """Dispatch a memory subcommand; returns an exit code (0 = ok)."""
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(MEMORY_USAGE)
        return 0
    command, rest = args[0], args[1:]
    if command == "show":
        memory_block = memory.injection_text()
        stdout.write(memory_block if memory_block else "(memory is empty)\n")
        return 0
    if command == "add":
        if not rest:
            stdout.write("Usage: memory add <text>\n")
            return 1
        stdout.write(memory.add_entry(memory.memory_path(), " ".join(rest)) + "\n")
        return 0
    if command == "remove":
        if len(rest) != 1:
            stdout.write("Usage: memory remove <substring>\n")
            return 1
        stdout.write(memory.remove_entry(memory.memory_path(), rest[0]) + "\n")
        return 0
    if command == "user":
        if rest and rest[0] == "add" and len(rest) > 1:
            stdout.write(memory.add_entry(memory.user_path(), " ".join(rest[1:])) + "\n")
            return 0
        stdout.write("Usage: memory user add <text>\n")
        return 1
    stdout.write(f"Unknown memory command: {command}\n\n{MEMORY_USAGE}")
    return 1


SKILL_USAGE = """\
Usage: skill <command> [args]

Commands:
  list                        show all skills with trigger
  view <name>                 show a skill's full content
  new <name> --trigger T      create a skill skeleton
      [--description D]
  remove <name>               delete a skill
"""


def run_skill_command(args: list[str], stdout: TextIO | None = None) -> int:
    """Dispatch a skill subcommand; returns an exit code (0 = ok)."""
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(SKILL_USAGE)
        return 0
    command, rest = args[0], args[1:]
    try:
        if command == "list":
            registry = skills.list_skills()
            if not registry:
                stdout.write("(no skills yet)\n")
                return 0
            for skill in registry:
                stdout.write(f"- {skill.name}: {skill.description} [trigger: {skill.trigger}]\n")
            return 0
        if command == "view":
            if len(rest) != 1:
                stdout.write("Usage: skill view <name>\n")
                return 1
            target = skills.skill_path(rest[0])
            if not target.exists():
                stdout.write(f"Error: skill '{rest[0]}' does not exist\n")
                return 1
            stdout.write(target.read_text(encoding="utf-8") + "\n")
            return 0
        if command == "new":
            if not rest:
                stdout.write("Usage: skill new <name> --trigger T [--description D]\n")
                return 1
            name = rest[0]
            try:
                flags = _parse_flags(rest[1:], ("trigger", "description"))
            except ValueError as exc:
                stdout.write(f"Error: {exc}\n")
                return 1
            if "trigger" not in flags:
                stdout.write("Error: --trigger is required\n")
                return 1
            skills.create_skill(
                name,
                flags.get("description", ""),
                flags["trigger"],
                body=f"# {name}\n\n(purpose)\n\n## Steps\n\n1. \n",
            )
            stdout.write(f"skill '{name}' created\n")
            return 0
        if command == "remove":
            if len(rest) != 1:
                stdout.write("Usage: skill remove <name>\n")
                return 1
            stdout.write(skills.remove_skill(rest[0]) + "\n")
            return 0
        stdout.write(f"Unknown skill command: {command}\n\n{SKILL_USAGE}")
        return 1
    except (cfg.ConfigError, skills.SkillError) as exc:
        stdout.write(f"Error: {exc}\n")
        return 1


SESSION_USAGE = """\
Usage: session <command> [args]

Commands:
  browse                     show the most recent sessions
  search <query>             full-text search across all sessions
  show <session-id>          show one session's messages
"""


def run_session_command(args: list[str], stdout: TextIO | None = None) -> int:
    """Dispatch a session subcommand; returns an exit code (0 = ok)."""
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(SESSION_USAGE)
        return 0
    command, rest = args[0], args[1:]
    if command == "browse":
        sessions = store.browse()
        if not sessions:
            stdout.write("(no sessions yet)\n")
            return 0
        for session in sessions:
            title = session.title or "(untitled)"
            stdout.write(
                f"{session.id}  {session.started_at}  {session.message_count:>3} msgs  {title}\n"
            )
        return 0
    if command == "search":
        if len(rest) < 1:
            stdout.write("Usage: session search <query>\n")
            return 1
        hits = store.search(" ".join(rest))
        if not hits:
            stdout.write(f"no sessions match: {' '.join(rest)}\n")
            return 0
        for hit in hits:
            stdout.write(
                f"{hit.session_id}  {hit.started_at}  ({hit.matches} hits)  {hit.title}\n"
            )
            if hit.snippet:
                stdout.write(f"    …{hit.snippet}…\n")
        return 0
    if command == "show":
        if len(rest) != 1:
            stdout.write("Usage: session show <session-id>\n")
            return 1
        messages = store.show(rest[0])
        if not messages:
            stdout.write(f"Error: no session with id {rest[0]}\n")
            return 1
        for message in messages:
            stdout.write(f"[{message['role']}] {message['content']}\n")
        return 0
    stdout.write(f"Unknown session command: {command}\n\n{SESSION_USAGE}")
    return 1


PERMISSIONS_USAGE = """\
Usage: permissions <command> [args]

Commands:
  status                     show mode and rules
  mode <m>                   ask | allow_all | read_only | deny_all
  allow <regex>              add an allow rule (matches tool call text)
  deny <regex>               add a deny rule (wins over allow)
  unallow <regex>            remove an allow rule
  undeny <regex>             remove a deny rule
  reset                      back to ask / no rules
"""


def run_permissions_command(args: list[str], stdout: TextIO | None = None) -> int:
    """Manage permission modes and rules (C1)."""
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(PERMISSIONS_USAGE)
        return 0
    command, rest = args[0], args[1:]
    try:
        if command == "status":
            perm = cfg.load_config().get("permissions", {}) or {}
            stdout.write(f"mode: {perm.get('mode', 'ask')}\n")
            stdout.write(f"allow: {perm.get('allow', [])}\n")
            stdout.write(f"deny: {perm.get('deny', [])}\n")
            return 0
        if command == "mode":
            if len(rest) != 1:
                stdout.write("Usage: permissions mode <ask|allow_all|read_only|deny_all>\n")
                return 1
            permissions.write_permissions_config(mode=rest[0])
            stdout.write(f"permission mode: {rest[0]}\n")
            return 0
        if command == "allow":
            if len(rest) != 1:
                stdout.write("Usage: permissions allow <regex>\n")
                return 1
            permissions.write_permissions_config(add_allow=rest[0])
            stdout.write(f"allow rule added: {rest[0]}\n")
            return 0
        if command == "deny":
            if len(rest) != 1:
                stdout.write("Usage: permissions deny <regex>\n")
                return 1
            permissions.write_permissions_config(add_deny=rest[0])
            stdout.write(f"deny rule added: {rest[0]}\n")
            return 0
        if command == "unallow":
            permissions.write_permissions_config(remove_allow=rest[0] if rest else "")
            stdout.write(f"allow rule removed: {rest[0] if rest else ''}\n")
            return 0
        if command == "undeny":
            permissions.write_permissions_config(remove_deny=rest[0] if rest else "")
            stdout.write(f"deny rule removed: {rest[0] if rest else ''}\n")
            return 0
        if command == "reset":
            permissions.write_permissions_config(reset=True)
            stdout.write("permissions reset to defaults\n")
            return 0
    except ValueError as exc:
        stdout.write(f"Error: {exc}\n")
        return 1
    stdout.write(f"Unknown permissions command: {command}\n\n{PERMISSIONS_USAGE}")
    return 1


JOB_USAGE = """\
Usage: job <command> [args]

Commands:
  list                        show all jobs
  add <id> --schedule <cron> --prompt <text>
                              add a scheduled job (cron: "0 9 * * *")
  remove <id>                 delete a job
  pause <id> | resume <id>    enable/disable a job
  run <id>                    run a job now (writes its log)
"""


def run_job_command(args: list[str], stdout: TextIO | None = None) -> int:
    """Manage scheduled jobs (C2)."""
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(JOB_USAGE)
        return 0
    command, rest = args[0], args[1:]
    if command == "list":
        jobs = cron.load_jobs()
        if not jobs:
            stdout.write("(no jobs yet)\n")
            return 0
        for job in jobs:
            state = "enabled" if job.enabled else "paused"
            stdout.write(
                f"{job.id}  [{state}]  {job.schedule}  last: {job.last_run or '-'}\n"
            )
        return 0
    if command == "add":
        if len(rest) < 3:
            stdout.write("Usage: job add <id> --schedule <cron> --prompt <text>\n")
            return 1
        job_id = rest[0]
        schedule = ""
        deliver = "log"
        prompt_parts: list[str] = []
        index = 1
        while index < len(rest):
            if rest[index] == "--schedule" and index + 1 < len(rest):
                schedule = rest[index + 1]
                index += 2
            elif rest[index] == "--deliver" and index + 1 < len(rest):
                deliver = rest[index + 1]
                index += 2
            elif rest[index] == "--prompt":
                index += 1
                while index < len(rest):
                    prompt_parts.append(rest[index])
                    index += 1
            else:
                index += 1
        try:
            message = cron.add_job(job_id, schedule, " ".join(prompt_parts), deliver)
        except ValueError as exc:
            stdout.write(f"Error: {exc}\n")
            return 1
        stdout.write(f"{message}\n")
        return 0
    if command == "remove":
        if len(rest) != 1:
            stdout.write("Usage: job remove <id>\n")
            return 1
        stdout.write(f"{cron.remove_job(rest[0])}\n")
        return 0
    if command in ("pause", "resume"):
        if len(rest) != 1:
            stdout.write(f"Usage: job {command} <id>\n")
            return 1
        stdout.write(f"{cron.set_enabled(rest[0], command == 'resume')}\n")
        return 0
    if command == "run":
        if len(rest) != 1:
            stdout.write("Usage: job run <id>\n")
            return 1
        try:
            output = cron.run_job_by_id(rest[0])
        except Exception as exc:  # subprocess timeouts etc.
            stdout.write(f"Error: job failed: {exc}\n")
            return 1
        stdout.write(f"{output}\n(log: {cron.job_log_path(rest[0])})\n")
        return 0
    stdout.write(f"Unknown job command: {command}\n\n{JOB_USAGE}")
    return 1


MCP_USAGE = """\
Usage: mcp <command> [args]

Commands:
  list                          show configured MCP servers
  add <name> --command <cmd> [--args ...]
                                register a stdio MCP server
  add <name> --url <url> [--transport http|sse]
                                register a remote MCP server
  import <file.json | inline-json>
                                import servers from mcpServers JSON
                                (Claude/Cursor format; existing names
                                are overwritten)
  remove <name>                 unregister a server
"""


def run_mcp_command(args: list[str], stdout: TextIO | None = None) -> int:
    """Manage MCP servers (C3)."""
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(MCP_USAGE)
        return 0
    command, rest = args[0], args[1:]
    conf = cfg.load_config()
    servers = dict((conf.get("mcp", {}) or {}).get("servers", {}) or {})
    if command == "list":
        if not servers:
            stdout.write("(no servers yet)\n")
            return 0
        for name, entry in servers.items():
            if entry.get("url"):
                transport = entry.get("transport", "http")
                stdout.write(f"{name}  url: {entry['url']}  transport: {transport}\n")
            else:
                stdout.write(
                    f"{name}  command: {entry.get('command')} {entry.get('args', [])}\n"
                )
        return 0
    if command == "import":
        if len(rest) != 1:
            stdout.write("Usage: mcp import <file.json | inline-json>\n")
            return 1
        raw = rest[0]
        if Path(raw).exists():
            try:
                raw = Path(raw).read_text(encoding="utf-8")
            except OSError as exc:
                stdout.write(f"Error: cannot read {rest[0]}: {exc}\n")
                return 1
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            stdout.write(f"Error: invalid JSON: {exc}\n")
            return 1
        if not isinstance(data, dict):
            stdout.write("Error: expected an object (mcpServers map)\n")
            return 1
        server_map = data.get("mcpServers", data)
        if not isinstance(server_map, dict):
            stdout.write("Error: 'mcpServers' must be an object\n")
            return 1
        added = updated = skipped = 0
        for name, entry in server_map.items():
            if not isinstance(entry, dict) or (
                not entry.get("command") and not entry.get("url")
            ):
                skipped += 1
                continue
            if name in servers:
                updated += 1
            else:
                added += 1
            clean: dict[str, Any] = {}
            if entry.get("command"):
                clean["command"] = str(entry["command"])
                clean["args"] = [str(a) for a in (entry.get("args") or [])]
            if entry.get("url"):
                clean["url"] = str(entry["url"])
                if entry.get("transport"):
                    clean["transport"] = str(entry["transport"])
            servers[name] = clean
        conf.setdefault("mcp", {})["servers"] = servers
        cfg.save_config(conf)
        stdout.write(
            f"imported {added + updated} servers (added {added}, "
            f"updated {updated}, skipped {skipped})\n"
        )
        return 0
    if command == "add":
        if len(rest) < 3:
            stdout.write("Usage: mcp add <name> --command <cmd> [--args ...]\n")
            return 1
        name = rest[0]
        cmd_args: list[str] = []
        index = 1
        while index < len(rest):
            if rest[index] == "--command" and index + 1 < len(rest):
                cmd_args.append(rest[index + 1])
                index += 2
            elif rest[index] == "--args":
                index += 1
                while index < len(rest):
                    cmd_args.append(rest[index])
                    index += 1
            else:
                index += 1
        if not cmd_args:
            stdout.write("Error: --command is required\n")
            return 1
        servers[name] = {"command": cmd_args[0], "args": cmd_args[1:]}
        conf.setdefault("mcp", {})["servers"] = servers
        cfg.save_config(conf)
        stdout.write(f"server '{name}' added\n")
        return 0
    if command == "remove":
        if len(rest) != 1 or rest[0] not in servers:
            stdout.write(f"Error: no server: {rest[0] if rest else ''}\n")
            return 1
        del servers[rest[0]]
        conf.setdefault("mcp", {})["servers"] = servers
        cfg.save_config(conf)
        stdout.write(f"server '{rest[0]}' removed\n")
        return 0
    stdout.write(f"Unknown mcp command: {command}\n\n{MCP_USAGE}")
    return 1


def run_provider_command(args: list[str], stdout: TextIO | None = None) -> int:
    """Dispatch a provider subcommand; returns an exit code (0 = ok)."""
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(PROVIDER_USAGE)
        return 0
    command, rest = args[0], args[1:]
    try:
        if command == "list":
            return _cmd_provider_list(stdout)
        if command == "add":
            return _cmd_provider_add(rest, stdout)
        if command == "remove":
            return _cmd_provider_remove(rest, stdout)
        if command == "set-key":
            return _cmd_provider_set_key(rest, stdout)
        stdout.write(f"Unknown provider command: {command}\n\n{PROVIDER_USAGE}")
        return 1
    except cfg.ConfigError as exc:
        stdout.write(f"Error: {exc}\n")
        return 1


def run_model_command(args: list[str], stdout: TextIO | None = None) -> int:
    """Dispatch a model subcommand; returns an exit code (0 = ok)."""
    stdout = stdout or sys.stdout
    if not args or args[0] in ("help", "--help", "-h"):
        stdout.write(MODEL_USAGE)
        return 0
    command, rest = args[0], args[1:]
    try:
        if command == "list":
            return _cmd_model_list(stdout)
        if command == "add":
            return _cmd_model_add(rest, stdout)
        if command == "set-default":
            return _cmd_model_set_default(rest, stdout)
        if command == "set-fallback":
            return _cmd_model_set_fallback(rest, stdout)
        if command == "ping":
            return _cmd_model_ping(rest, stdout)
        stdout.write(f"Unknown model command: {command}\n\n{MODEL_USAGE}")
        return 1
    except cfg.ConfigError as exc:
        stdout.write(f"Error: {exc}\n")
        return 1
