"""MCP-description prompt-injection scan (Phase G.8, Plan G v5).

A compromised MCP server can inject instructions in tool descriptions.
Hermes scans every description when the MCP client connects; eaccode
does the same here. Findings are added to a per-server report and the
user is warned via a banner before the tools are exposed.

Mirrors the pattern from Hermes' tools/mcp_tool.py:_scan_mcp_description.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class DescriptionFinding:
    """One prompt-injection finding in an MCP tool description."""

    rule_id: str
    severity: str   # HIGH / MEDIUM / LOW
    snippet: str    # the offending phrase (truncated)


@dataclass
class DescriptionScanReport:
    """Aggregated scan result for one MCP server."""

    server_name: str
    findings: list[DescriptionFinding] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.findings

    def format(self) -> str:
        if self.is_clean:
            return f"[ok] MCP server {self.server_name!r}: descriptions clean."
        head = f"[warn] MCP server {self.server_name!r}: {len(self.findings)} finding(s)"
        body = "\n".join(
            f"  - [{f.severity}] {f.rule_id}: {f.snippet!r}" for f in self.findings
        )
        return f"{head}\n{body}"


# Patterns that smell like prompt-injection attempts. Hermes uses more
# (anomalyco/opencode has a full prompt-injection corpus). We cover the
# high-signal patterns here; expanding to the full corpus can wait.
_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "ignore_previous_instructions",
        "HIGH",
        re.compile(
            r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?"
            r"(?:previous|prior|above|system)\s+(?:instructions?|prompts?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "you_are_now",
        "HIGH",
        re.compile(r"\byou\s+are\s+now\s+(?:a|an|the)\s+\w+", re.IGNORECASE),
    ),
    (
        "exfiltrate_env",
        "HIGH",
        re.compile(
            r"\b(?:cat|print|echo|read|send|exfiltrate|leak)\s+"
            r"(?:.*)?(?:\.env|process\.env|secrets?|tokens?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "system_role_assignment",
        "MEDIUM",
        re.compile(
            r"\b(?:system\s+prompt|assistant\s+role|<\|system\|>|<\|assistant\|>)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ssh_or_credential_paths",
        "HIGH",
        re.compile(
            r"~?/?\.ssh/(?:id_rsa|id_ed25519|authorized_keys|config)|"
            r"~?/?\.aws/(?:credentials|config)|"
            r"~?/?\.netrc|~?/?\.npmrc|~?/?\.pypirc",
            re.IGNORECASE,
        ),
    ),
    (
        "hidden_instructions_marker",
        "MEDIUM",
        re.compile(
            r"\b(?:do\s+not\s+(?:tell|show|reveal|mention|disclose)\s+the\s+user)\b|"
            r"\b(?:secret|hidden|covert)\s+instruction\b",
            re.IGNORECASE,
        ),
    ),
]


def scan_description(server_name: str, tool_name: str, description: str) -> list[DescriptionFinding]:
    """Scan a single MCP tool description for prompt-injection patterns.

    Returns a list of findings (empty if clean).
    """
    if not description:
        return []
    findings: list[DescriptionFinding] = []
    for rule_id, severity, pattern in _RULES:
        match = pattern.search(description)
        if match:
            snippet = match.group(0)
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            findings.append(
                DescriptionFinding(
                    rule_id=f"mcp-{server_name}-{tool_name}-{rule_id}",
                    severity=severity,
                    snippet=snippet,
                )
            )
    return findings


def scan_server(server_name: str, tools: Iterable[tuple[str, str]]) -> DescriptionScanReport:
    """Scan every (tool_name, description) tuple for one server.

    Hermes runs this on MCP-connect; we expose it as a helper for the
    eaccode MCP integration to call.
    """
    report = DescriptionScanReport(server_name=server_name)
    for tool_name, description in tools:
        report.findings.extend(scan_description(server_name, tool_name, description))
    return report
