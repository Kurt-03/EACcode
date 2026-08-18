"""Permission system (Phase C1): rule-based access control for agent tools.

Three modes (Hermes-compatible):
- manual: every mutating tool prompts the user on every call
- smart: aux LLM risk-assesses commands; safe auto-approve, dangerous ask
- off:   auto-approve everything (yolo mode)

Rule order: deny rules always win, allow rules second, then the mode, then ask.

Hardline patterns (catastrophic destruction) block regardless of mode.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from eaccode import config as cfg

# Hermes-compatible mode names. Old names (ask, allow_all, read_only, deny_all)
# are still accepted as aliases for backward compatibility.
MODES = ("smart", "manual", "off")
_MODE_ALIASES: dict[str, str] = {
    "ask": "manual",
    "allow_all": "off",
    "read_only": "off",  # handled separately below
    "deny_all": "manual",  # we never truly disable tools — blocked via mode
}

# Tools that never mutate anything (safe under read_only mode).
READ_ONLY_TOOLS = frozenset(
    {
        "read_file",
        "list_files",
        "search_files",
        "http_get",
        "web_search",
        "current_time",
        "system_info",
        "session_search",
        "session_scroll",
        "list_skills",
        "list_models",
        "model_ping",
        "repo_scan",
        "repo_search",
        "repo_context",
        "git_status",
        "git_log",
        "git_diff",
        "browser_status",
    }
)

# Read-only MCP tools are detected by their name (the MCP protocol marks
# them readOnlyHint; we approximate via verbs). Anything else from an MCP
# server counts as mutating -> always ask.
_READONLY_MCP_HINTS = (
    "get_",
    "list_",
    "read",
    "search",
    "inspect",
    "grep",
    "scan",
    "show",
    "find",
    "state",
    "status",
    "console",
)


def _is_readonly_mcp(tool_name: str) -> bool:
    """True when an mcp__<server>__<tool> name looks read-only."""
    if not tool_name.startswith("mcp__"):
        return False
    tool = tool_name.split("__", 2)[-1].lower()
    return any(hint in tool for hint in _READONLY_MCP_HINTS)


# Truly dangerous tools: always prompt, approval is never remembered.
ALWAYS_ASK_TOOLS = frozenset(
    {
        "run_command",
        "browser_click",
        "browser_type",
        "browser_navigate",
        "browser_screenshot",
    }
)


def is_always_ask(tool_name: str) -> bool:
    """Critical tools prompt on every call (no session memory)."""
    return tool_name in ALWAYS_ASK_TOOLS or (
        tool_name.startswith("mcp__") and not _is_readonly_mcp(tool_name)
    )


# ---------------------------------------------------------------------------
# Hermes-Verbatim Patterns (battle-tested in production)
# ---------------------------------------------------------------------------

# Command-position anchor for hardline rules. `rm` etc. must be the
# actual command word, not data inside another command's argument.
_CMDPOS = (
    r'(?:^|[\n`]|$\()'            # start position
    r'\s*'                          # optional whitespace
    r'(?:sudo\s+(?:-[^\s]+\s+)*)?'  # optional sudo with flags
    r'(?:env\s+(?:\w+=\S*\s+)*)?'   # optional env with VAR=VAL pairs
    r'(?:(?:exec|nohup|setsid|time)\s+)*'  # optional wrapper commands
    r'\s*'
)


def _hardline_rm_path(path_alt: str, tail: str = r'(?:\s|$|[)`;|&])') -> str:
    """Match rm path either quoted or bare with terminator."""
    return rf'(?:["\']?(?:{path_alt})["\']?|(?:{path_alt}){tail})'


_HARDLINE_SYSTEM_DIRS = (
    r'/home|/home/\*|/root|/root/\*|/etc|/etc/\*|/usr|/usr/\*|'
    r'/var|/var/\*|/bin|/bin/\*|/sbin|/sbin/\*|/boot|/boot/\*|/lib|/lib/\*'
)

_RM_FLAG_PREFIX = _CMDPOS + r'rm\s+(-[^\s]*\s+)*'

XDG_SYSTEM_PATH = (
    r'(?:/etc/|/usr/|/var/|/bin/|/sbin/|/lib/|/boot/|/opt/|/sys/|/proc/)'
)

SSH_SENSITIVE_PATH = (
    r'(?:~|/\w+)/(?:\.ssh|\.gnupg)(?:/[\w.\-]+)*'
)

CREDENTIAL_FILES = (
    r'(?:~|/\w+)/\.'  # home directory
    r'(?:netrc|pgpass|npmrc|pypirc|aws/credentials|huggingface/token)'
    r'(?:\s|$|["\'`;|])'
)

SHELL_RC_FILES = (
    r'(?:~|/\w+)/\.'
    r'(?:bashrc|zshrc|profile|bash_profile|zprofile)'
    r'(?:\s|$|["\'`;|])'
)

SENSITIVE_PATHS = (
    rf'\.git/'    # git history
    rf'/\.ssh/'   # SSH keys
    rf'/\.env(\.\w+)?$|/^\.env$|\.env(\.\w+)?$'  # secrets
    rf'config\.yaml$'                             # eaccode config
    rf'authorized_keys$|id_rsa(\.pub)?$'          # SSH files
)

# ---------------------------------------------------------------------------
# Hardline patterns (12 from Hermes, always block regardless of mode)
# ---------------------------------------------------------------------------

HARDLINE_PATTERNS: list[tuple[str, str]] = [
    (
        _RM_FLAG_PREFIX + _hardline_rm_path(r'/(?:(?:\.\.?)?/)*(?:\.\.?)?\**|/ \*'),
        "recursive delete of root filesystem",
    ),
    (
        _RM_FLAG_PREFIX + _hardline_rm_path(_HARDLINE_SYSTEM_DIRS),
        "recursive delete of system directory",
    ),
    (
        _RM_FLAG_PREFIX + _hardline_rm_path(r'(?:~|\$\{?HOME\}?)(?:/?|/\*)?'),
        "recursive delete of home directory",
    ),
    (r'\bmkfs(\.[a-z0-9]+)?\b', "format filesystem (mkfs)"),
    (
        r'\bdd\b[^\n]*\bof=/dev/(sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*',
        "dd to raw block device",
    ),
    (
        r'>\s*/dev/(sd|nvme|hd|mmcblk|vd|xvd)[a-z0-9]*\b',
        "redirect to raw block device",
    ),
    (r':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:', "fork bomb"),
    (r'\bkill\s+(-[^\s]+\s+)*-1\b', "kill all processes"),
    (
        _CMDPOS + r'(shutdown|reboot|halt|poweroff)\b',
        "system shutdown/reboot",
    ),
    (_CMDPOS + r'init\s+[06]\b', "init 0/6 (shutdown/reboot)"),
    (
        _CMDPOS + r'systemctl\s+(poweroff|reboot|halt|kexec)\b',
        "systemctl poweroff/reboot",
    ),
    (_CMDPOS + r'telinit\s+[06]\b', "telinit 0/6 (shutdown/reboot)"),
]

# Compiled at module load for hot-path speed
_RE_FLAGS = re.IGNORECASE | re.DOTALL
HARDLINE_PATTERNS_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, _RE_FLAGS), description)
    for pattern, description in HARDLINE_PATTERNS
]

# ---------------------------------------------------------------------------
# Dangerous patterns (77 from Hermes, routed through aux LLM in smart mode)
# ---------------------------------------------------------------------------

DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    # Recursive delete (substantive targets)
    (r'\brm\s+(-[rRfi]+\s+)*[~]', "force recursive delete of home dir"),
    (r'\brm\s+(-[rRfi]+\s+)*\.\s*$', "recursive delete of cwd"),
    # chmod 777
    (r'\bchmod\s+(-[rR]+\s+)*777\b', "chmod 777 (world-writable)"),
    # Curl pipe to shell
    (r'\b(curl|wget)\b.*\s*\|\s*(sh|bash|zsh|python|node)\b',
     "remote script via pipe"),
    # Find -exec -rm/-delete
    (r'\bfind\b.*-exec(?:dir)?\s+rm\b', "find -exec rm"),
    (r'\bfind\b.*-delete\b', "find -delete"),
    # Docker / Podman lifecycle
    (r'\bdocker\s+(restart|stop|kill)\b', "docker lifecycle"),
    (r'\bdocker\s+compose\s+(restart|stop|down)\b', "docker compose lifecycle"),
    (r'\bpodman\s+(restart|stop|kill)\b', "podman lifecycle"),
    # Docker daemon redirect (remote control)
    (r'\bdocker\s+(?:-{1,2}\S+(?:[=\s]\S+)?\s+)*(?:-h|--host)[=\s]+\S+',
     "docker with remote daemon redirect"),
    (r'\bdocker\s+(?:-{1,2}\S+(?:[=\s]\S+)?\s+)*(?:-c|--context)[=\s]+\S+',
     "docker with daemon redirect"),
    # Network exfiltration
    (r'\bnc\s+(?:-[a-z]+\s+)*\S*\s+-', "netcat listener"),
    (r'\bcurl\s+.*\s*--upload-file\b', "curl upload-file"),
    (r'\bcurl\s+.*\s*-T\b', "curl upload"),
    # Encryption / ransomware precursors
    (r'\bgpg\s+.*--batch.*--yes.*--(?:symmetric|encrypt)\b', "gpg encrypt batch"),
    (r'\bopenssl\s+enc\b.*\s+-[aes]\b', "openssl encrypt"),
    # Pipe to shell (general)
    (r'\|\s*(sh|bash|zsh|dash|ksh)\b', "pipe to shell"),
    # Eval/exec dynamic
    (r'\beval\s+', "eval statement"),
    (r'\bexec\s+', "exec statement"),
    # Cron / systemd manipulation
    (r'\bcrontab\s+-(?:e|lr)\b', "crontab edit"),
    (r'\bsystemctl\s+(enable|disable|mask|unmask)\b', "systemctl unit change"),
    # Network config
    (r'\bip\s+(?:addr|link|route)\b.*\s+(?:add|del|flush)\b', "ip command modification"),
    (r'\biptables\s+', "iptables modification"),
    (r'\bnft\s+', "nftables modification"),
    # Disk operations
    (r'\bparted\s+', "parted disk operation"),
    (r'\bfdisk\s+/dev/', "fdisk raw device"),
    # Sensitive file edits
    (rf'\b(echo|cat|tee)\b.*\s*>\s*["\']?{SSH_SENSITIVE_PATH}',
     "redirect to SSH path"),
    (rf'\b(echo|cat|tee)\b.*\s*>\s*["\']?{CREDENTIAL_FILES}',
     "redirect to credentials file"),
    (rf'\b(echo|cat|tee)\b.*\s*>\s*["\']?{SHELL_RC_FILES}',
     "redirect to shell RC file"),
    (rf'\b(echo|cat|tee)\b.*\s*>\s*["\']?{XDG_SYSTEM_PATH}',
     "redirect to system file"),
    # In-place edits that mutate sensitive targets
    (rf'\bsed\s+-i\b.*\s+["\']?{SSH_SENSITIVE_PATH}', "sed in-place on SSH path"),
    (rf'\bsed\s+-i\b.*\s+["\']?{CREDENTIAL_FILES}', "sed in-place on credentials"),
    # Find + chmod / find + rm short forms
    (r'\bfind\b.*-exec\s+chmod\b', "find -exec chmod"),
    (r'\bfind\b.*\s+-execdir\s+rm\b', "find -execdir rm"),
    # Disk fill
    (r'\bdd\s+.*\s+of=/dev/zero\b', "dd from /dev/zero"),
    (r'\btruncate\s+-s\s+\d+[GTP]\b', "truncate to large size"),
    # Permission 0o777 / 0o666
    (r'\b0?o?777\b', "octal 777"),
    (r'\b0?o?666\b', "octal 666"),
    # Sudo variations
    (r'\bsudo\s+(?!-S|-A|--stdin|--askpass)', "sudo without -S"),
    (r'\bsudo\s+-S\b', "sudo -S (password via stdin)"),
    (r'\bsudo\s+-A\b', "sudo -A (askpass)"),
    (r'\bsudo\s+--stdin\b', "sudo --stdin"),
    (r'\bsudo\s+--askpass\b', "sudo --askpass"),
    # Disk operations on raw devices
    (r'\bmkfs(\.[a-z0-9]+)?\b.*\s+/dev/(sd|hd|nvme|vd)', "mkfs on raw device"),
    # Kernel module loading
    (r'\binsmod\s+', "kernel module insertion"),
    (r'\bmodprobe\s+', "kernel module load"),
    # Self-termination
    (r'\b(pkill|killall|taskkill)\b.*\b(eaccode)\b', "kill eaccode process"),
    (r'\bkill\s+.*\$\(\s*pgrep\b', "kill via pgrep"),
    # Fork bomb variants
    (r'\bwhile\s+true\b.*\s+(:\(\))', "while true fork bomb"),
    # rm -rf with brace expansion
    (r'\brm\s+.*\{[^}]*,[^}]*\}', "rm with brace expansion"),
    # Sudo rm
    (r'\bsudo\s+rm\b', "sudo rm"),
    # Delete all hidden files
    (r'\brm\s+.*\.\*', "delete hidden files"),
    # Reset git hard
    (r'\bgit\s+reset\s+--hard\b', "git reset hard"),
    (r'\bgit\s+clean\s+-fd\b', "git clean force"),
    (r'\bgit\s+push\s+.*--force\b', "git push force"),
    # Force overwrite
    (r'\bmv\s+.*-f\b.*\s+/etc/', "force move to /etc"),
    (r'\bcp\s+.*-f\b.*\s+/etc/', "force copy to /etc"),
    # Send to background and detach
    (r'\bnohup\b.*\s+&\s*$', "nohup background"),
    (r'\bdisown\b', "disown process"),
    # curl|bash one-liner
    (r'\bcurl\s+.*\s*\|\s*bash\b', "curl pipe to bash"),
    (r'\bcurl\s+.*\s*\|\s*sh\b', "curl pipe to sh"),
    # Subshell with destructive
    (r'\$\(.*\brm\s+.*-rf\b', "subshell rm -rf"),
    # rm -rf with redirection in tail
    (r'\brm\s+-rf\b.*\s*&&.*\s+(?!cat|ls)', "rm -rf chained"),
    # Overwrite via tee
    (r'\btee\s+.*\s*/etc/', "tee to /etc"),
    (r'\btee\s+.*\s*/var/', "tee to /var"),
    # Path traversal
    (r'\.\.[\\/]\.\.[\\/]', "path traversal"),
    # SSH private key operations
    (r'\bchmod\s+.*\bid_rsa\b', "chmod on SSH key"),
    (r'\bcat\s+.*\s+>\s*.*\.ssh/', "cat to .ssh"),
    # Sudo with echo (passwd injection)
    (r'\becho\s+.*\s*\|\s*sudo\s+-S\b', "echo pipe to sudo -S"),
    # Process kill on system
    (r'\bkill\s+-9\s+1\b', "kill init"),
    (r'\bkill\s+-SIGTERM\s+1\b', "kill SIGTERM init"),
    # env reset
    (r'\benv\s+-i\b', "env -i"),
    # File system flush
    (r'\bsync\s*;\s*echo\s+.*\s+>\s*/proc/sysrq', "sync to sysrq"),
    # Disable SELinux/AppArmor
    (r'\bsetenforce\s+0\b', "disable SELinux"),
    (r'\bsetenforce\s+Permissive\b', "set SELinux permissive"),
    (r'\bapparmor_parser\s+-R\b', "remove AppArmor profile"),
]

DANGEROUS_PATTERNS_COMPILED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, _RE_FLAGS), description)
    for pattern, description in DANGEROUS_PATTERNS
]

# ---------------------------------------------------------------------------
# Decision + PermissionManager
# ---------------------------------------------------------------------------


@dataclass
class Decision:
    """Result of a permission check."""

    allow: bool
    reason: str
    mode: str = "smart"
    smart_reviewed: bool = False


class PermissionManager:
    """Central permission gate for all agent tools."""

    def __init__(
        self,
        conf: dict[str, Any] | None = None,
        ask_handler: Callable[[str, dict[str, Any]], bool] | None = None,
        smart_reviewer: Callable[[str, str], str] | None = None,
    ) -> None:
        self.conf = conf
        self.mode = "smart"
        self.allow_rules: list[str] = []
        self.deny_rules: list[str] = []
        self.ask_handler = ask_handler
        self.smart_reviewer = smart_reviewer
        self._ask_lock = threading.Lock()
        self._session_allowed: set[str] = set()
        self._init_from_config()

    def _init_from_config(self) -> None:
        source = self.conf if self.conf is not None else cfg.load_config()
        perm = (source or {}).get("permissions", {}) or {}
        raw_mode = perm.get("mode")
        # Resolve mode aliases
        if raw_mode in _MODE_ALIASES:
            resolved = _MODE_ALIASES[raw_mode]
            if raw_mode == "read_only":
                # Promote read_only to a special mode
                self.mode = "read_only"
            else:
                self.mode = resolved
        elif raw_mode in MODES or raw_mode == "read_only":
            self.mode = raw_mode
        else:
            self.mode = "smart"
        self.allow_rules = list(perm.get("allow", []) or [])
        self.deny_rules = list(perm.get("deny", []) or [])

    def call_text(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """The string rules match against (tool + sorted json args)."""
        return f"{tool_name} {json.dumps(arguments, sort_keys=True, ensure_ascii=False)}"

    def session_allow(self, tool_name: str) -> None:
        """Remember an approval for the rest of this process session."""
        self._session_allowed.add(tool_name)

    def session_clear(self) -> None:
        """Forget all session approvals."""
        self._session_allowed.clear()

    def session_allowed(self) -> list[str]:
        """Currently session-approved tool names (sorted)."""
        return sorted(self._session_allowed)

    def check(self, tool_name: str, arguments: dict[str, Any]) -> Decision:
        """Decide whether a tool call may run."""
        call = self.call_text(tool_name, arguments)
        for rule in self.deny_rules:
            if re.search(rule, call, re.IGNORECASE):
                return Decision(False, f"denied by rule: {rule}", self.mode)
        for rule in self.allow_rules:
            if re.search(rule, call, re.IGNORECASE):
                return Decision(True, f"allowed by rule: {rule}", self.mode)

        # read_only mode: only read-only tools
        if self.mode == "read_only":
            if tool_name in READ_ONLY_TOOLS or _is_readonly_mcp(tool_name):
                return Decision(True, "mode=read_only (read-only tool)", self.mode)
            return Decision(
                False, f"mode=read_only blocks write tool: {tool_name}", self.mode
            )

        # deny_all: nothing works
        if self.mode == "deny_all":
            return Decision(False, "mode=deny_all blocks everything", self.mode)

        # Hardline: always block, regardless of mode
        # Check ONLY the command argument (not the full call text), so
        # _CMDPOS anchors work correctly.
        if tool_name == "run_command":
            import json as _json
            command_arg = arguments.get("command", "")
            # Reconstruct just the command text for matching
            bare_call = command_arg if isinstance(command_arg, str) else ""
            for regex, description in HARDLINE_PATTERNS_COMPILED:
                # Match against either the bare command or the full call
                if regex.search(bare_call) or regex.search(call):
                    return Decision(
                        False, f"hardline blocked: {description}", self.mode
                    )

        # Smart mode: aux LLM risk assessment
        if self.mode == "smart" and tool_name == "run_command":
            command_arg = arguments.get("command", "")
            bare_call = command_arg if isinstance(command_arg, str) else ""
            found_dangerous = False
            for regex, description in DANGEROUS_PATTERNS_COMPILED:
                if regex.search(bare_call) or regex.search(call):
                    found_dangerous = True
                    return self._smart_review(tool_name, arguments, description)
            if not found_dangerous:
                # Safe command: auto-approve
                return Decision(
                    True, "smart mode: safe command", self.mode
                )

        # Read-only tools run freely (smart mode also)
        if tool_name in READ_ONLY_TOOLS:
            return Decision(
                True, "read-only tool (no approval needed)", self.mode
            )
        if _is_readonly_mcp(tool_name):
            return Decision(
                True, "read-only mcp tool (no approval needed)", self.mode
            )

        # off mode: auto-approve everything
        if self.mode == "off":
            return Decision(True, "mode=off (auto-approve)", self.mode)

        # Session-allowed tools
        if tool_name in self._session_allowed:
            return Decision(True, "approved for this session", self.mode)

        # Ask user
        if self.ask_handler is not None:
            with self._ask_lock:
                allowed = self.ask_handler(tool_name, arguments)
            if allowed and not is_always_ask(tool_name):
                self._session_allowed.add(tool_name)
            return Decision(
                allowed,
                "approved by user" if allowed else "denied by user",
                self.mode,
            )
        return Decision(
            False, "no permission handler set (deny by default)", self.mode
        )

    def _smart_review(
        self, tool_name: str, arguments: dict[str, Any], description: str
    ) -> Decision:
        """Route a dangerous-pattern command through the aux LLM."""
        if self.smart_reviewer is None:
            # No smart reviewer registered → fall back to ask
            return self._ask_user(tool_name, arguments, fallback_reason="smart")
        command = arguments.get("command", "")
        verdict = self.smart_reviewer(command, description)
        if verdict == "approve":
            return Decision(
                True,
                f"smart-approved: {description}",
                self.mode,
                smart_reviewed=True,
            )
        if verdict == "deny":
            return Decision(
                False,
                f"smart-denied: {description}",
                self.mode,
                smart_reviewed=True,
            )
        # escalate or unknown → ask user
        return self._ask_user(tool_name, arguments, fallback_reason=f"smart: {verdict}")

    def _ask_user(
        self, tool_name: str, arguments: dict[str, Any], fallback_reason: str
    ) -> Decision:
        """Ask user via the registered handler."""
        if self.ask_handler is None:
            return Decision(
                False, f"{fallback_reason}: no handler", self.mode
            )
        with self._ask_lock:
            allowed = self.ask_handler(tool_name, arguments)
        if allowed and not is_always_ask(tool_name):
            self._session_allowed.add(tool_name)
        return Decision(
            allowed,
            "approved by user" if allowed else "denied by user",
            self.mode,
        )


def mode_hint(mode: str) -> str:
    """System-prompt hint so the agent knows its permission mode upfront."""
    if mode == "smart":
        return (
            "\n\n## Permission mode: SMART\n"
            "Safe tool calls auto-approve. Commands matching a dangerous pattern "
            "(rm -rf, chmod 777, curl|sh, etc.) are reviewed by a security "
            "LLM; clearly safe commands run, clearly dangerous ones are blocked, "
            "and uncertain ones ask the user. Hardline patterns (rm -rf /, "
            "sudo -S, shutdown, fork bombs) are blocked automatically. Sensitive "
            "paths (`.git/`, `.ssh/`, `.env`, `config.yaml`) still prompt.\n"
            "Tip: /approvals to see or change mode."
        )
    if mode == "manual":
        return (
            "\n\n## Permission mode: MANUAL\n"
            "Every mutating tool call prompts the user. Read-only tools (read, "
            "search, web, time, sessions, git read, repo tools, read-only MCP) "
            "run freely. Critical tools (run_command, browser actions, mutating "
            "MCP) prompt on every call.\n"
            "Tip: /approvals smart to switch to smart mode."
        )
    if mode == "off":
        return (
            "\n\n## Permission mode: AUTO-APPROVE (yolo)\n"
            "All tool calls are approved automatically. You may use any tool "
            "freely. Hardline patterns (rm -rf /, sudo -S, shutdown) still block.\n"
            "Tip: /approvals smart for safe auto-approve."
        )
    if mode == "read_only":
        return (
            "\n\n## Permission mode: READ-ONLY\n"
            "You are in read-only mode: do NOT attempt any tool that writes, "
            "creates or deletes (write_file, run_command, create_skill, "
            "memory_*, spawn_subagent, mcp tools that mutate). Read/search/web "
            "tools are fine. If the user asks for changes, explain that "
            "read-only mode blocks them."
        )
    return ""


def write_permissions_config(
    mode: str | None = None,
    add_allow: str | None = None,
    add_deny: str | None = None,
    remove_allow: str | None = None,
    remove_deny: str | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    """Persist permission settings into config.yaml; returns the new section."""
    conf = cfg.load_config()
    perm = dict(conf.get("permissions", {}) or {})
    if reset:
        perm = {"mode": "smart", "allow": [], "deny": []}
    if mode is not None:
        if mode not in MODES and mode not in ("read_only",):
            raise ValueError(
                f"unknown mode: {mode} (use one of {', '.join(MODES + ('read_only',))})"
            )
        perm["mode"] = mode
    if add_allow:
        rules = list(perm.get("allow", []) or [])
        if add_allow not in rules:
            rules.append(add_allow)
        perm["allow"] = rules
    if add_deny:
        rules = list(perm.get("deny", []) or [])
        if add_deny not in rules:
            rules.append(add_deny)
        perm["deny"] = rules
    if remove_allow:
        perm["allow"] = [r for r in perm.get("allow", []) or [] if r != remove_allow]
    if remove_deny:
        perm["deny"] = [r for r in perm.get("deny", []) or [] if r != remove_deny]
    conf["permissions"] = perm
    cfg.save_config(conf)
    return perm
