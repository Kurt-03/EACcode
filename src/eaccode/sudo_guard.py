"""Sudo-stdin-guard (Phase 1, H7, Hermes-Verbatim).

Detects when the model pipes a password to `sudo -S`, `sudo --stdin`,
`sudo -A`, or `sudo --askpass`. These patterns are NEVER legitimate for
the agent — there is no use-case where the agent should be feeding a
password to sudo automatically. We MUST detect these BEFORE the
yolo/smart-mode/off-mode bypasses so a runaway agent cannot escalate
privileges silently.

Matched patterns:
  - sudo -S / --stdin (password via stdin)
  - sudo -A / --askpass (askpass helper)
  - echo PASSWORD | sudo -S ... (password-injection one-liner)
  - echo $PASSWORD | sudo -A ... (same)
  - rm / chmod / dd / any | sudo ... (chained sudo-from-stdin)
  - "password", "passwd", "pwd" piped to sudo -S
"""

from __future__ import annotations

import re
from typing import Pattern

# Hermes-Verbatim: only the EXPLICIT password-feeding flags are caught
# by the stdin-guard. General sudo is blocked elsewhere (hardline +
# dangerous-patterns in permissions.py DANGEROUS_SUDO).
_SUDO_STDIN_PATTERNS: list[tuple[Pattern[str], str]] = [
    # sudoreplay and sudo itself with stdin flags
    (re.compile(r"\bsudo\s+-S\b", re.IGNORECASE), "sudo -S (password via stdin)"),
    (re.compile(r"\bsudo\s+-A\b", re.IGNORECASE), "sudo -A (askpass helper)"),
    (re.compile(r"\bsudo\s+--stdin\b", re.IGNORECASE), "sudo --stdin (password via stdin)"),
    (re.compile(r"\bsudo\s+--askpass\b", re.IGNORECASE), "sudo --askpass (custom helper)"),
    # Echo-pipe password-injection one-liners
    (re.compile(r"\becho\s+.*\s*\|\s*sudo\s+-S\b", re.IGNORECASE), "echo piped to sudo -S"),
    (re.compile(r"\becho\s+.*\s*\|\s*sudo\s+-A\b", re.IGNORECASE), "echo piped to sudo -A"),
    # Variable/password-feeling pipes
    (re.compile(r"\b(password|passwd|pwd)\b[^\n]*\|\s*sudo\s+-S\b", re.IGNORECASE), "password piped to sudo -S"),
    (re.compile(r"\$\{?\w*PASSWORD\}?[^\n]*\|\s*sudo\s+-S\b", re.IGNORECASE), "password env-var piped to sudo -S"),
]


def is_sudo_stdin_guess(command: str) -> tuple[bool, str]:
    """True when command pipes a password to sudo stdin (NEVER safe).

    Returns ``(True, description)`` for matches, ``(False, "")`` for safe
    commands. Detection order: first match wins (deterministic).
    """
    if not command:
        return False, ""
    for pattern, description in _SUDO_STDIN_PATTERNS:
        if pattern.search(command):
            return True, description
    return False, ""
