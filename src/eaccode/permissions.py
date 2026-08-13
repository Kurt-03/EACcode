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
    }
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
        if self.ask_handler is not None:
            allowed = self.ask_handler(tool_name, arguments)
            return Decision(
                allowed,
                "approved by user" if allowed else "denied by user",
                "ask",
            )
        return Decision(
            False, "no permission handler set (deny by default)", "ask"
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
