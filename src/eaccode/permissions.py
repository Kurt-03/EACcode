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

# READ_ONLY_TOOLS is gone. The canonical read-only detection now lives in
# the mutates tag on each Tool (set per make_*_tools() factory). For
# check() which only has the tool_name string, we fall back to the static
# _READ_ONLY_TOOL_NAMES list below.

def is_read_only_tool(tool: Any) -> bool:
    """True when the given Tool is read-only (does not mutate state)."""
    return bool(getattr(tool, "mutates", False)) is False


# Fallback name list - mirrors the mutates=False tools at audit time
# (08-18). Update whenever new mutates=False tools are added.
_READ_ONLY_TOOL_NAMES = frozenset({
    "read_file", "list_files", "search_files",
    "http_get", "web_search", "current_time", "system_info",
    "session_search", "session_scroll",
    "list_skills", "list_models", "model_ping",
    "repo_scan", "repo_search", "repo_context",
    "git_status", "git_log", "git_diff",
    "browser_status",
})

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

# Module-level regex flags (used everywhere a pattern is compiled).
_RE_FLAGS = re.IGNORECASE | re.DOTALL

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

# Sensitive-path patterns used by the runtime check (08-18 hardened).
# Match the touched-by-write paths: any .ssh/*, .env, .git/ (config / refs),
# config.yaml, authorized_keys, etc.
SENSITIVE_PATH_PATTERNS = (
    r"/\.ssh/",
    r"/\.gnupg/",
    r"/\.aws/",
    r"/\.kube/",
    r"/\.docker/",
    r"/\.netrc",
    r"/\.pgpass",
    r"/\.npmrc",
    r"/\.pypirc",
    r"/\.bashrc",
    r"/\.zshrc",
    r"/\.profile",
    r"/\.bash_profile",
    r"/\.zprofile",
    r"/\.git/config",
    r"/\.git/HEAD",
    r"/\.git/index",
    r"/\.git/refs/",
    r"/\.git/objects/",
    r"\.env$",
    r"\.env\.\w+$",
    r"/\.env",
    r"config\.yaml$",
    r"authorized_keys$",
    r"id_rsa(\.pub)?$",
    r"/etc/",
    r"/usr/",
    r"/var/",
    r"/bin/",
    r"/sbin/",
    r"/boot/",
    r"/lib/",
    r"/sys/",
    r"/proc/",
    r"/root/",
)

SENSITIVE_PATH_PATTERNS_COMPILED: list = [
    re.compile(pattern, _RE_FLAGS) for pattern in SENSITIVE_PATH_PATTERNS
]


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
    """Result of a permission check.

    Attributes:
        allow: True if the call may proceed, False otherwise.
        reason: Human-readable description of why (used in UI/logs).
        mode: Permission mode under which the decision was made.
        scope: Lifetime of approval if allow=True:
                - "once": just this call
                - "session": all calls of this kind for the rest of the session
                - "always": persistent config rule
        smart_reviewed: True when an aux LLM was consulted.
        owner_override: True when smart-mode routed to user because the
                aux LLM was uncertain (different UI: "once/deny" only).
        timeout: True when user did not answer in time (fail-closed).
    """

    allow: bool
    reason: str
    mode: str = "smart"
    scope: str = "once"
    smart_reviewed: bool = False
    owner_override: bool = False
    timeout: bool = False


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

    def _extract_path_arg(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Find a filesystem path in arguments, regardless of param name."""
        for key in ("path", "file_path", "target_path", "p", "filepath"):
            value = arguments.get(key)
            if isinstance(value, str) and value:
                return value
        # Special-case: patch_multiple has edits (list of dicts with 'path')
        if tool_name == "patch_multiple":
            edits = arguments.get("edits", [])
            if isinstance(edits, list) and edits:
                first = edits[0]
                if isinstance(first, dict):
                    value = first.get("path")
                    if isinstance(value, str):
                        return value
        return ""

    def check(self, tool_name: str, arguments: dict[str, Any]) -> Decision:
        """Decide whether a tool call may run.

        Pipeline (08-18 hardened by audit):
          1. deny rule (wins against allow rule)
          2. allow rule
          3. read_only mode: only mutating=False tools run freely
          4. Hardline pattern: always block run_command matches
          5. Sensitive-path: prompt on writes to .ssh/, .env, config.yaml etc.
          6. Smart-Mode Aux-LLM: only for mutating AND not-always-ask tools
          7. Read-only tools: auto-approve
          8. off mode: auto-approve everything (hardline still blocks)
          9. Session-allowed: auto-approve
         10. ask_handler (manual mode default)
        """
        call = self.call_text(tool_name, arguments)
        for rule in self.deny_rules:
            if re.search(rule, call, re.IGNORECASE):
                return Decision(False, f"denied by rule: {rule}", self.mode)
        for rule in self.allow_rules:
            if re.search(rule, call, re.IGNORECASE):
                return Decision(True, f"allowed by rule: {rule}", self.mode)
        # Phase C.8: persistent deny_always blocks (Hermes-Verbatim)
        if self._check_blocked_persistent(call):
            return Decision(False, "denied: persistent block list match", self.mode)

        # 3. read_only mode
        if self.mode == "read_only":
            # We do NOT have a Tool instance here; fall back to pattern check
            ro_markers = (
                "read", "list", "search", "extract", "status",
                "get", "time", "info", "scan", "grep",
            )
            if any(tool_name.startswith(m) or m in tool_name.lower() for m in ro_markers):
                return Decision(True, "mode=read_only (heuristic)", self.mode)
            return Decision(
                False, f"mode=read_only blocks write tool: {tool_name}", self.mode
            )

        # 4a. Command normalization + parser-limit (Phase 1, H4/H5/H6)
        if tool_name == "run_command":
            from eaccode.command_normalize import (
                _command_parser_limit_exceeded,
                normalize_command_for_detection,
            )
            command_arg = arguments.get("command", "")
            bare_call = command_arg if isinstance(command_arg, str) else ""
            if _command_parser_limit_exceeded(bare_call):
                return Decision(
                    False,
                    "command too complex to safely analyze (parser limit)",
                    self.mode,
                )
            # Use the normalized form for downstream pattern matching
            normalized = normalize_command_for_detection(bare_call)
            bare_call = normalized

        # 4b. Sudo-stdin-guard (Phase 1, H7) - BEFORE hardline
        if tool_name == "run_command":
            from eaccode.sudo_guard import is_sudo_stdin_guess

            command_arg = arguments.get("command", "")
            bare_call = command_arg if isinstance(command_arg, str) else ""
            is_sudo_guess, sudo_guess_desc = is_sudo_stdin_guess(bare_call)
            if is_sudo_guess:
                return Decision(
                    False,
                    f"sudo-stdin blocked: {sudo_guess_desc}",
                    self.mode,
                )

        # 4. Hardline (only run_command, same as before)
        if tool_name == "run_command":
            command_arg = arguments.get("command", "")
            bare_call = command_arg if isinstance(command_arg, str) else ""
            for regex, description in HARDLINE_PATTERNS_COMPILED:
                if regex.search(bare_call) or regex.search(call):
                    return Decision(
                        False, f"hardline blocked: {description}", self.mode
                    )

        # 5. Sensitive-path check (for any tool with a path arg)
        path_arg = self._extract_path_arg(tool_name, arguments)
        if path_arg:
            # 5a. Phase 2: file_safety.hardcoded-paths (more strict than our
            # generic regex match). Block unconditionally - no prompt.
            # Only check on mutating tools (writing to file).
            _mutating_tools = (
                "write_file", "patch_file", "patch_multiple",
                "file_edit", "git_commit", "git_branch_new",
                "git_commit_undo", "create_skill", "improve_skill",
                "memory_add", "memory_replace", "memory_remove",
                "memory_apply_batch", "browser_screenshot",
            )
            if tool_name in _mutating_tools:
                try:
                    from eaccode.file_safety import is_write_denied

                    if is_write_denied(path_arg):
                        return Decision(
                            False,
                            "file_safety blocked (exact sensitive path)",
                            self.mode,
                        )
                except Exception:
                    pass
            # 5b. Generic sensitive-path check. SKIP for read-only tools -
            # reading /home/user/.ssh/ is fine (no mutation possible).
            # The write-side block is already covered by file_safety above.
            if tool_name not in _READ_ONLY_TOOL_NAMES and not _is_readonly_mcp(
                tool_name
            ):
                if self._is_sensitive_path(path_arg):
                    return self._ask_user(
                        tool_name,
                        arguments,
                        fallback_reason="sensitive path",
                        sensitive=True,
                    )

        # 6. Smart-Mode Aux-LLM for mutating, non-always-ask tools.
        # Coverage: run_command + mutating path-args (write_file etc.)
        # Phase F (smart-mode coverage):
        # We pass tool_description + arguments (JSON-serialized) to the aux
        # LLM so it can review any mutating action, not just bash.
        needs_aux_review = False
        aux_description = ""
        aux_command_text = ""

        if self.mode == "smart" and tool_name == "run_command":
            needs_aux_review = True
            aux_description = "run_command"
            aux_command_text = arguments.get("command", "")
        elif self.mode == "smart" and tool_name in (
            "write_file", "patch_file", "patch_multiple",
            "file_edit", "git_commit", "git_branch_new",
            "git_commit_undo", "create_skill", "improve_skill",
            "memory_add", "memory_replace", "memory_remove",
            "memory_apply_batch", "browser_screenshot",
        ):
            needs_aux_review = True
            aux_description = tool_name
            aux_command_text = call  # Already JSON-serialized call_text

        if needs_aux_review:
            for regex, description in DANGEROUS_PATTERNS_COMPILED:
                if regex.search(aux_command_text) or regex.search(call):
                    return self._smart_review(tool_name, arguments, description)
            # No dangerous pattern: auto-approve in smart mode
            return Decision(True, "smart mode: safe action", self.mode)

        # 7. Read-only tools (heuristic — same as before, list of names)
        if tool_name in _READ_ONLY_TOOL_NAMES:
            return Decision(True, "read-only tool", self.mode)
        if _is_readonly_mcp(tool_name):
            return Decision(
                True, "read-only mcp tool (no approval needed)", self.mode
            )

        # 8. off mode: auto-approve
        if self.mode == "off":
            return Decision(True, "mode=off (auto-approve)", self.mode)

        # 9. Session-approved tools
        if tool_name in self._session_allowed and not is_always_ask(tool_name):
            return Decision(True, "approved for this session", self.mode)

        # 10. ask_handler (5 outcomes: once/session/always/deny/deny_always/timeout)
        return self._ask_user(
            tool_name,
            arguments,
            fallback_reason=f"mode={self.mode}",
        )

    def _is_sensitive_path(self, path: str) -> bool:
        """True when a write-target path is in a sensitive location.

        Sensitive = credentials / ssh keys / shell rc / system dirs / config.
        Used as a smart-mode sanity-check on tools that take a path argument.

        Path is resolved with Path.resolve() to defeat ../-traversal tricks.
        We check the ORIGINAL path first (cheap), then the resolved path.
        """
        if not path:
            return False
        if self._path_matches_sensitive(path):
            return True
        resolved = self._resolve_path(path)
        if resolved != path and self._path_matches_sensitive(resolved):
            return True
        return False

    @staticmethod
    def _resolve_path(path: str) -> str:
        try:
            from pathlib import Path as _Path

            return str(_Path(path).resolve())
        except Exception:
            return path

    @staticmethod
    def _path_matches_sensitive(path: str) -> bool:
        for pattern in SENSITIVE_PATH_PATTERNS_COMPILED:
            if pattern.search(path):
                return True
        return False

    def _smart_review(
        self, tool_name: str, arguments: dict[str, Any], description: str
    ) -> Decision:
        """Route a dangerous-pattern command through the aux LLM.

        Aux LLM can return (Hermes-Verbatim):
          - "approve"       auto-approved, scope=once
          - "deny"          blocked, smart_reviewed=True
          - "escalate"      user-prompted once/session/always/deny/deny_always
          - "owner_override" Aux LLM uncertain; user gets only once/deny
        """
        if self.smart_reviewer is None:
            # No smart reviewer registered → fall back to ask
            return self._ask_user(tool_name, arguments, fallback_reason="smart")
        # Build the input string the aux LLM reviews. For run_command we
        # send the command verbatim; for all other tools we send the
        # full call_text (tool + json args) so the aux LLM sees the path,
        # the new content, etc.
        import json as _json
        if tool_name == "run_command":
            review_input = arguments.get("command", "")
        else:
            try:
                review_input = _json.dumps(arguments, sort_keys=True)
            except Exception:
                review_input = str(arguments)
        verdict = self.smart_reviewer(review_input, description)
        if verdict == "approve":
            return Decision(
                True,
                f"smart-approved: {description}",
                self.mode,
                scope="once",
                smart_reviewed=True,
            )
        if verdict == "deny":
            return Decision(
                False,
                f"smart-denied: {description}",
                self.mode,
                smart_reviewed=True,
            )
        if verdict == "owner_override":
            # Owner-override: Aux LLM uncertain, user must decide
            # but only once/deny (no permanent allow).
            return self._ask_user(
                tool_name,
                arguments,
                fallback_reason=f"smart owner-override: {verdict}",
                smart_denied=True,
            )
        # escalate or unknown → ask user
        return self._ask_user(tool_name, arguments, fallback_reason=f"smart: {verdict}")

    def _ask_user(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        fallback_reason: str,
        *,
        smart_denied: bool = False,
        sensitive: bool = False,
    ) -> Decision:
        """Ask user via the registered handler.

        The ask_handler is called and returns one of:
          - ("once", True)
          - ("session", True)
          - ("always", True)
          - ("deny", False)
          - ("deny_always", False)
          - ("timeout", False)   (only set by the palette wrapper)
          - True/False backwards-compat ("y"/"yes"=once, anything else=deny)

        smart_denied: True when AUX-LLM flagged the call as risky but
            gave no clear ban. Show only once/deny (no permanent allow).
        sensitive: True when on a sensitive-path write. Same UI as
            normally, just different reason prefix.
        """
        if self.ask_handler is None:
            # Fail-closed: deny immediately if no handler is wired (avoids
            # the prompt_toolkit input() deadlock Hermes documented in
            # `tools.approval._prompt_dangerous_approval_inner`).
            return Decision(
                False,
                f"{fallback_reason}: no handler (deny-by-default)",
                self.mode,
                timeout=False,
            )

        with self._ask_lock:
            result = self.ask_handler(tool_name, arguments)

        scope, allowed = self._normalize_ask_result(result)
        # ALWAYS_ASK_TOOLS = no session memory (every call prompts)
        # Once = no session memory
        # Session/Always = session memory
        if allowed and scope in ("session", "always"):
            if not is_always_ask(tool_name):
                self._session_allowed.add(tool_name)
        if allowed and scope == "always":
            self._add_allow_rule(tool_name, arguments)
        if (not allowed) and scope == "deny_always":
            self._add_deny_rule(tool_name, arguments, fallback_reason)
        # Backward-compat: legacy True from ask_handler (scope=once) ALSO
        # adds to session if not in ALWAYS_ASK_TOOLS (matches the prior
        # behavior expected by tests).
        if allowed and scope == "once" and not is_always_ask(tool_name):
            self._session_allowed.add(tool_name)

        reason = self._reason_for(scope, fallback_reason)
        return Decision(
            allow=allowed,
            reason=reason,
            mode=self.mode,
            scope=scope,
            owner_override=smart_denied,
        )

    @staticmethod
    def _normalize_ask_result(result: Any) -> tuple[str, bool]:
        """Accept the legacy bool OR the new (scope, allow) tuple."""
        if isinstance(result, tuple) and len(result) == 2:
            scope, allowed = result
            return str(scope), bool(allowed)
        # Legacy y/n fallback
        if isinstance(result, bool):
            return ("once", result)
        if isinstance(result, str):
            # Map shortcuts
            mapping = {
                "y": ("once", True), "yes": ("once", True),
                "n": ("once", False), "no": ("once", False),
                "s": ("session", True),
                "a": ("always", True),
                "A": ("deny_always", False),
            }
            if result in mapping:
                return mapping[result]
        return ("once", False)  # safe default

    @staticmethod
    def _reason_for(scope: str, fallback_reason: str) -> str:
        table = {
            "once": f"{fallback_reason}: once approved",
            "session": f"{fallback_reason}: approved for session",
            "always": f"{fallback_reason}: approved permanently",
            "deny": f"{fallback_reason}: denied once",
            "deny_always": f"{fallback_reason}: denied permanently",
        }
        return table.get(scope, fallback_reason)

    def _add_allow_rule(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Persist an allow rule for this tool-name (used by 'a')."""
        import re as _re  # noqa
        import json as _json  # noqa

        call = self.call_text(tool_name, arguments)
        try:
            escaped = _re.escape(call[:200])
            if escaped not in self.allow_rules:
                self.allow_rules.append(escaped)
                self._save_rules()
        except Exception:
            pass

    def _add_deny_rule(self, tool_name: str, arguments: dict[str, Any], reason: str) -> None:
        """Persist a deny rule (called on 'A' / deny_always).

        Two locations:
          1. `permissions.deny` in config.yaml (legacy per-config-rule)
          2. blocked.py store on disk (Phase C.8 persistent list)
        """
        import re as _re

        call = self.call_text(tool_name, arguments)
        try:
            escaped = _re.escape(call[:200])
            if escaped not in self.deny_rules:
                self.deny_rules.append(escaped)
                self._save_rules()
        except Exception:
            pass

        # Persistent block list (Hermes-Verbatim):
        try:
            from eaccode.blocked import add_blocked as _add_blocked

            _add_blocked(call[:200], reason or "permanent deny", tool_name)
        except Exception:
            pass

    def _check_blocked_persistent(self, call_text: str) -> bool:
        """True when call_text matches a pattern in blocked.json (Hermes-Verbatim)."""
        try:
            from eaccode.blocked import find_blocked as _find_blocked

            return _find_blocked(call_text) is not None
        except Exception:
            return False

    def _save_rules(self) -> None:
        """Persist updated allow/deny rules to config.yaml."""
        from eaccode import config as cfg

        try:
            data = cfg.load_config()
            data.setdefault("permissions", {})
            data["permissions"]["allow"] = list(self.allow_rules)
            data["permissions"]["deny"] = list(self.deny_rules)
            cfg.save_config(data)
        except Exception:
            pass


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
