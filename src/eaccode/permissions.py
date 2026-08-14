"""Permission system (Phase C1): rule-based access control for agent tools.

Ask-by-default with explicit modes and regex rules. Every tool call passes
through ``PermissionManager.check`` before execution. Rule order:
deny rules always win, then allow rules, then the mode, then ask.

Sandbox note: a kernel sandbox (Docker/bwrap) is documented but not
implemented yet — on Windows the protection model is deny-first modes
(read_only/deny_all) plus the interactive ask handler.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from eaccode import config as cfg

MODES = ("ask", "allow_all", "read_only", "deny_all")

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


@dataclass
class Decision:
    """Result of a permission check."""

    allow: bool
    reason: str
    mode: str = "ask"


@dataclass
class PermissionManager:
    """Central permission gate for all agent tools."""

    conf: dict[str, Any] | None = None
    mode: str = "ask"
    allow_rules: list[str] = field(default_factory=list)
    deny_rules: list[str] = field(default_factory=list)
    ask_handler: Callable[[str, dict[str, Any]], bool] | None = None
    _ask_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _session_allowed: set[str] = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        source = self.conf if self.conf is not None else cfg.load_config()
        perm = (source or {}).get("permissions", {}) or {}
        self.mode = perm.get("mode", "ask")
        if self.mode not in MODES:
            self.mode = "ask"
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
        if self.mode == "deny_all":
            return Decision(False, "mode=deny_all blocks everything", self.mode)
        if self.mode == "read_only" and tool_name not in READ_ONLY_TOOLS:
            return Decision(
                False, f"mode=read_only blocks write tool: {tool_name}", self.mode
            )
        if self.mode == "read_only":
            return Decision(True, "mode=read_only (read-only tool)", self.mode)
        if self.mode == "allow_all":
            return Decision(True, "mode=allow_all", self.mode)
        if self.mode == "ask" and tool_name in READ_ONLY_TOOLS:
            # read-only tools run freely; only mutating tools need approval
            return Decision(
                True, "read-only tool (no approval needed)", self.mode
            )
        if self.mode == "ask" and _is_readonly_mcp(tool_name):
            # MCP tools whose name marks them read-only run freely too
            return Decision(
                True, "read-only mcp tool (no approval needed)", self.mode
            )
        if tool_name in self._session_allowed:
            return Decision(True, "approved for this session", self.mode)
        if self.ask_handler is not None:
            # serialized: parallel tool calls must not race the stdin prompt
            with self._ask_lock:
                allowed = self.ask_handler(tool_name, arguments)
            if allowed and not is_always_ask(tool_name):
                # routine tools: one approval covers the whole session;
                # critical tools (shell, browser actions, mutating MCP)
                # keep prompting on every call
                self._session_allowed.add(tool_name)
            return Decision(
                allowed,
                "approved by user" if allowed else "denied by user",
                "ask",
            )
        return Decision(
            False, "no permission handler set (deny by default)", "ask"
        )


def mode_hint(mode: str) -> str:
    """System-prompt hint so the agent knows its permission mode upfront."""
    if mode == "read_only":
        return (
            "\n\n## Permission mode: READ-ONLY\n"
            "You are in read-only mode: do NOT attempt any tool that writes, "
            "creates or deletes (write_file, run_command, create_skill, "
            "memory_*, spawn_subagent, mcp tools that mutate). Read/search/web "
            "tools are fine. If the user asks for changes, explain that "
            "read-only mode blocks them."
        )
    if mode == "deny_all":
        return (
            "\n\n## Permission mode: DENY-ALL\n"
            "No tools are available. Answer from knowledge only and tell the "
            "user the permission mode blocks tool use."
        )
    if mode == "allow_all":
        return (
            "\n\n## Permission mode: AUTO-APPROVE\n"
            "All tool calls are approved automatically. You may use any tool "
            "freely."
        )
    return (
        "\n\n## Permission mode: ASK\n"
        "Read-only tools (read_file, search, web, time, sessions, git read, "
        "repo tools, read-only MCP tools) run freely. Mutating tools "
        "(write_file, memory, skills, git_commit, tests, subagents) prompt "
        "ONCE per session - after approval they run freely until eaccode "
        "restarts. Critical tools (run_command, browser actions, mutating "
        "MCP calls) prompt on EVERY call.\n"
        "Proceed normally."
    )


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
        perm = {"mode": "ask", "allow": [], "deny": []}
    if mode is not None:
        if mode not in MODES:
            raise ValueError(f"unknown mode: {mode} (use one of {', '.join(MODES)})")
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
