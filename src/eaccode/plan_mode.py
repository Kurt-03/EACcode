"""Plan mode (Plan I P1.6).

Three states the agent can be in:
- ``off``   - everything is permitted (legacy behaviour, default for non-shell tools)
- ``manual`` - every mutating action triggers a y/n user prompt
- ``smart`` - dangerous actions trigger an Aux-LLM review, then ask user
- ``plan``  - only read-only tools are allowed; write tools are blocked

The ``plan`` mode is the entry point to the Plan-Mode workflow:

  1. User runs eaccode in plan mode.
  2. Model uses only read tools to explore the repo.
  3. Model formulates a plan (a single ``<plan>...</plan>`` block).
  4. User reviews the plan with ``/plan show``.
  5. User approves with ``/plan approve`` - the agent re-enters
     ``manual`` or ``smart`` mode and can now execute the plan.

Plan approval is **explicit and reversible** - users can also
``/plan reject`` to stay in plan mode and revise the plan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


PLAN_MODE = "plan"
READ_ONLY_TOOLS = frozenset({
    "read_file",
    "list_files",
    "search_files",
    "repo_scan",
    "repo_search",
    "repo_context",
    "web_search",
    "http_get",
    "current_time",
    "system_info",
    "memory_read",
    "todo_read",
})


@dataclass
class PendingPlan:
    """A plan formulated by the model, awaiting user approval."""

    id: str
    body: str
    created_at: str
    source: str  # "foreground" | "background_review"

    def age_seconds(self) -> float:
        try:
            ts = datetime.fromisoformat(self.created_at)
        except ValueError:
            return 0.0
        return (datetime.now() - ts).total_seconds()


_PLAN_RE = re.compile(r"<plan>(.*?)</plan>", re.DOTALL | re.IGNORECASE)


def extract_plan_from_text(text: str) -> Optional[str]:
    """Extract a ``<plan>...</plan>`` block from the model's output."""
    m = _PLAN_RE.search(text)
    if m:
        return m.group(1).strip()
    return None


def is_read_only_tool(tool_name: str) -> bool:
    """True when ``tool_name`` is allowed in plan mode."""
    return tool_name in READ_ONLY_TOOLS


def can_use_in_plan(tool_name: str) -> bool:
    """Same as ``is_read_only_tool`` but with a clearer name for callers."""
    return is_read_only_tool(tool_name)


def is_plan_blocked_tool(tool_name: str) -> bool:
    """True when ``tool_name`` is blocked in plan mode (mutating tools)."""
    return not is_read_only_tool(tool_name)


def explain_plan_block(tool_name: str) -> str:
    """Human-readable explanation for a blocked tool in plan mode."""
    return (
        f"tool '{tool_name}' is blocked in plan mode. "
        "Run `/plan approve` first to exit plan mode and execute the plan."
    )


__all__ = [
    "PLAN_MODE",
    "READ_ONLY_TOOLS",
    "PendingPlan",
    "extract_plan_from_text",
    "is_read_only_tool",
    "can_use_in_plan",
    "is_plan_blocked_tool",
    "explain_plan_block",
]