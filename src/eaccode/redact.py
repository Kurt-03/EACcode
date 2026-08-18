"""Secret/PII redaction for permission prompts.

The redaction happens ONLY for display (what the user sees). The original
command is still what executes after approval. Reuses the Hermes pattern:
mask credentials, jwt tokens, AWS/GitHub keys while leaving the first
3-4 chars visible for identification (so the user still knows which key
they are approving).

08-18: deep permissions hardening (Plan C).
"""

from __future__ import annotations

import re
from typing import Pattern


# Compiled patterns. Order matters - more specific patterns first.
# Each redactor also has a human-readable tag.

_PATTERNS: list[tuple[str, str]] = [
    # GitHub personal access tokens (ghp_)
    (r"ghp_[A-Za-z0-9]{20,}", "gh"),
    # GitHub OAuth (gho_/ghs_/ghu_/ghr_)
    (r"gho_[A-Za-z0-9]{20,}", "gh-oauth"),
    (r"ghs_[A-Za-z0-9]{20,}", "gh-secret"),
    (r"ghu_[A-Za-z0-9]{20,}", "gh-user"),
    (r"ghr_[A-Za-z0-9]{20,}", "gh-refresh"),
    # GitHub fine-grained (github_pat_)
    (r"github_pat_[A-Za-z0-9_]{20,}", "gh-fine"),
    # sk- prefixed keys - generic (OpenAI-style and Anthropic-style)
    # Distinguish by length and prefix - both masked as "openai"
    (r"sk-(?:ant-|proj-)?[A-Za-z0-9\-]{20,}", "openai"),
    # AWS access keys (AKIA...)
    (r"AKIA[0-9A-Z]{16}", "aws-key"),
    # AWS secret keys (heuristic only - 40-char base64)
    (r"(?<=[\"': =])([A-Za-z0-9/+=]{40})(?=[\"']) (?<!.\1)", "aws-secret"),
    # JWT (header.payload.signature)
    (r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", "jwt"),
    # Slack tokens (xoxb-, xoxp-, xoxa-)
    (r"xox[abprs]-[A-Za-z0-9-]{10,}", "slack"),
    # PEM private keys
    (
        r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----",
        "pem-key",
    ),
    # .env-style KEY=value pairs containing obvious secrets
    (
        r"(?i)(?:api_?key|secret|token|password|passwd|pwd|access_?token|auth_?token|bearer|private_?key)\s*[:=]\s*['\"]?([A-Za-z0-9\-_\./+=]{16,})['\"]?",
        "credential",
    ),
    # Bearer tokens in Authorization headers
    (r"(?i)Bearer\s+([A-Za-z0-9\-_\.~+\/]+=*)", "bearer"),
    # Generic long hex/base64 blobs (40+ chars, partial-match)
    (r"(?<![\w/+=])([A-Za-z0-9+/]{40,}=*)(?![\w/+=])", "blob"),
]


class Redactor:
    """Replaces sensitive tokens in tool-arguments/command strings."""

    def __init__(self) -> None:
        self._compiled: list[tuple[Pattern[str], str]] = [
            (re.compile(pattern), tag) for pattern, tag in _PATTERNS
        ]

    def redact(self, text: str) -> str:
        """Return text with sensitive tokens masked.

        First 3 chars are kept (when present) so the user can identify what
        was masked.
        """
        if not text:
            return text
        for pattern, tag in self._compiled:
            def _sub(match: re.Match[str]) -> str:
                full = match.group(0)
                # PEM blocks: replace whole block
                if tag == "pem-key":
                    return f"[REDACTED-{tag}]"
                # For captured groups inside parens, mask just the capture
                if match.lastindex and match.lastindex >= 1 and match.group(1):
                    captured = match.group(1)
                    prefix = full[: full.find(captured)]
                    if len(captured) > 8:
                        masked = captured[:3] + "***" + captured[-2:]
                    else:
                        masked = "***"
                    return prefix + masked + full[full.find(captured) + len(captured) :]
                # Whole-match mask
                if len(full) > 8:
                    return full[:3] + "***" + full[-2:]
                return f"[REDACTED-{tag}]"

            text = pattern.sub(_sub, text)
        return text


# Default global instance
_global = Redactor()


def redact(text: str) -> str:
    """Module-level helper - use this in product code."""
    return _global.redact(text)
