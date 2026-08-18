"""Skill AST audit (Phase G.9, Plan G v5).

Skills are user-installable bundles of prompt instructions. A malicious
skill can hide prompt-injection, exfiltration, or destructive code in
its body. Hermes scans every skill on install; eaccode does the same
here.

Mirrors tools/skills_guard.py:scan_skill.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


logger = logging.getLogger(__name__)


SEVERITY_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


@dataclass
class Finding:
    rule_id: str
    severity: str   # HIGH / MEDIUM / LOW
    title: str
    description: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
        }


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    skill_name: str = ""

    @property
    def has_high(self) -> bool:
        return any(f.severity == "HIGH" for f in self.findings)

    @property
    def is_clean(self) -> bool:
        return not self.findings

    def format(self) -> str:
        if self.is_clean:
            return f"[ok] skill {self.skill_name!r}: clean"
        head = f"[warn] skill {self.skill_name!r}: {len(self.findings)} finding(s)"
        body = "\n".join(
            f"  - [{f.severity}] {f.rule_id}: {f.title}" for f in self.findings
        )
        return f"{head}\n{body}"


# Pattern catalogue. Hermes' skills_guard has more (covers dozens of
# subtle patterns); we cover the high-signal ones.
_RULES: list[tuple[str, str, str, re.Pattern[str]]] = [
    (
        "ignore_previous",
        "HIGH",
        "Tells the model to ignore its real instructions",
        re.compile(
            r"\bignore\s+(?:all\s+)?(?:previous|prior|above|system)\s+instructions?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "exfil_env",
        "HIGH",
        "Reads .env or credential files",
        re.compile(
            r"(?:cat|read|open|send|exfiltrate|leak)\s+"
            r"(?:.*)?(?:\.env|process\.env|secrets?|tokens?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "shell_exec",
        "HIGH",
        "Spawns a shell or runs arbitrary code",
        re.compile(
            r"\b(?:os\.system|subprocess\.|popen|eval|exec)\s*\(",
            re.IGNORECASE,
        ),
    ),
    (
        "network_egress",
        "MEDIUM",
        "Hits the network from skill code",
        re.compile(
            r"\b(?:requests\.|urllib\.|httpx\.|fetch\(|http\.get)\s*",
            re.IGNORECASE,
        ),
    ),
    (
        "ssh_or_secret_paths",
        "HIGH",
        "Targets SSH keys or credential files",
        re.compile(
            r"~?/?\.ssh/(?:id_rsa|id_ed25519|authorized_keys|config)|"
            r"~?/?\.aws/(?:credentials|config)|"
            r"~?/?\.netrc|~?/?\.npmrc",
            re.IGNORECASE,
        ),
    ),
    (
        "system_role_override",
        "HIGH",
        "Attempts to redefine the assistant's role",
        re.compile(
            r"\byou\s+are\s+now\s+(?:a|an|the)\s+\w+|"
            r"\bforget\s+everything\b|"
            r"\bnew\s+system\s+prompt\b",
            re.IGNORECASE,
        ),
    ),
]


def _scan_content(content: str) -> list[Finding]:
    findings: list[Finding] = []
    for rule_id, severity, title, pattern in _RULES:
        if pattern.search(content):
            findings.append(
                Finding(
                    rule_id=f"skill-{rule_id}",
                    severity=severity,
                    title=title,
                    description=pattern.pattern,
                )
            )
    return findings


def scan_file(path: Path) -> list[Finding]:
    """Scan a single file (any kind of text)."""
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    return _scan_content(text)


def scan_skill(skill_path: Path, source: str = "community") -> ScanResult:
    """Scan every text file in a skill directory."""
    result = ScanResult(skill_name=skill_path.name)
    if skill_path.is_file():
        result.findings.extend(scan_file(skill_path))
        return result
    for path in skill_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in {
            ".md", ".py", ".sh", ".bash", ".txt", ".json", ".yaml", ".yml",
        }:
            result.findings.extend(scan_file(path))
    return result


def _content_digest(skill_path: Path) -> str:
    """Stable digest for caching scans across runs."""
    if skill_path.is_file():
        files = [skill_path]
    else:
        files = [p for p in skill_path.rglob("*") if p.is_file()]
    h = hashlib.sha256()
    for p in sorted(files):
        try:
            h.update(str(p.relative_to(skill_path)).encode())
            h.update(p.read_bytes())
        except OSError:
            continue
    return h.hexdigest()


# Caching layer. Keyed by skill path + content digest.
_CACHE: dict[tuple[str, str], ScanResult] = {}


def scan_skill_cached(skill_path: Path, source: str = "community") -> ScanResult:
    """Return a cached scan if the content digest is unchanged."""
    digest = _content_digest(skill_path)
    key = (str(skill_path), digest)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    result = scan_skill(skill_path, source=source)
    _CACHE[key] = result
    return result


def should_allow_install(result: ScanResult, force: bool = False) -> tuple[bool, str]:
    """Return (allowed, reason) for installing a skill with these findings."""
    if force:
        return True, "user-forced install"
    if result.is_clean:
        return True, "scan clean"
    if result.has_high:
        return False, (
            "Skill contains HIGH-severity findings. "
            "Use force=True to install anyway."
        )
    return True, "skill has MEDIUM/LOW findings; user must opt in"


def format_scan_report(result: ScanResult) -> str:
    return result.format()


def clear_cache() -> None:
    """Drop the scan cache (for tests / hot-reload)."""
    _CACHE.clear()
