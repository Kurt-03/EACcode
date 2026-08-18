"""Hermes cron + gateway + container detection (Phase 4, H13/H20/H21/H23).

eaccode-runs in different modes:
  - **Interactive CLI** — user is present, approval prompts make sense
  - **Cron job** — no user present, dangerous commands must auto-block
  - **Gateway** — remote protocol (ACP), approval prompts go through socket
  - **Container/sandbox** — env-marker `EACCODE_IN_CONTAINER=1`,
                             skip approval if host paths are NOT bind-mounted

Plus:
  - `approvals.cron_mode: deny | approve` config (Hermes-Verbatim H20)
  - `approve_known_safe_set` — list of commands that auto-allow (Hermes-Verbatim H21)
  - `_YOLO_MODE_FROZEN` — yolo-flag frozen at import-time (Hermes-Verbatim H24)
"""

from __future__ import annotations

import os
import threading
from typing import Optional


# -- Context detection (H13) ------------------------------------------

def is_cron_context() -> bool:
    """True when eaccode runs under cron (no TTY, EACCODE_CRON=1, etc.)."""
    if os.environ.get("EACCODE_CRON") == "1":
        return True
    if os.environ.get("EACCODE_IN_CRON") == "1":
        return True
    # Cron typically has no TTY
    try:
        return not os.isatty(0)
    except Exception:
        return False


def is_gateway_context() -> bool:
    """True when running under a remote protocol (ACP socket, etc.)."""
    return os.environ.get("EACCODE_GATEWAY") == "1"


def is_container_context() -> bool:
    """True when running inside a Docker/sandbox container (skip guards if no host bind-mounts)."""
    return (
        os.environ.get("EACCODE_IN_CONTAINER") == "1"
        or os.path.exists("/.dockerenv")
        or os.path.exists("/run/.containerenv")
    )


# -- Cron-mode config (H20) -------------------------------------------

def get_cron_approval_mode() -> str:
    """'deny' (default) | 'approve' from config.yaml approvals.cron_mode.

    In 'deny' mode, dangerous commands in cron jobs are blocked outright
    (no user present to approve).
    In 'approve' mode, they're flagged for review but allowed to execute.
    """
    try:
        from eaccode import config as cfg

        conf = cfg.load_config() or {}
        perms = conf.get("approvals", {}) or {}
        return (perms.get("cron_mode") or "deny").strip().lower()
    except Exception:
        return "deny"


# -- Known-safe set (H21) ---------------------------------------------

# Commands that are always safe (Hermes-Verbatim). Used for the
# `--yolo` / mode=off path: even smart-mode knows these don't need review.
KNOWN_SAFE_PATTERNS: tuple[str, ...] = (
    r"^pwd$",
    r"^echo\s+[^|;&$`'\"\\\(\)]{0,200}$",
    r"^true$",
    r"^false$",
    r"^:\s*$",
    # ls/cat in /tmp on read-only paths is fine (heuristic)
    r"^cat\s+/tmp/[\w\-.]{1,80}$",
    r"^cat\s+/dev/null$",
    # Python import-only (no execution): safe to introspect.
    r"^python[0-9.]*\s+-c\s+\"import\s+[\w.]+\"$",
    r"^python[0-9.]*\s+--version$",
    # git in safe directions
    r"^git\s+(status|log|diff|branch|show)\b",
)


# -- YOLO mode-frozen (H24) ------------------------------------------

_YOLO_LOCK = threading.Lock()
_YOLO_FROZEN: bool = False


def freeze_yolo_mode() -> None:
    """Freeze YOLO mode at process start.

    After this call, even mid-process skills cannot flip YOLO on/off.
    Hermes-Verbatim safety invariant. Idempotent.
    """
    global _YOLO_FROZEN
    with _YOLO_LOCK:
        _YOLO_FROZEN = True


def is_yolo_active() -> bool:
    """True when YOLO mode is requested via flag/env AND not yet frozen off."""
    if _YOLO_FROZEN:
        # Once frozen, YOLO cannot be re-enabled mid-process; check flag
        return False
    return (
        os.environ.get("EACCODE_YOLO") == "1"
        or os.environ.get("EACCODE_APPROVALS_OFF") == "1"
    )


def is_current_session_yolo_enabled() -> bool:
    """Per-session YOLO toggle (Hermes-Verbatim; differs from process YOLO).

    Allows the user to flip YOLO on for one session without it being a
    process-wide hazard.
    """
    # Session override via env that is REWRITABLE per turn.
    return os.environ.get("EACCODE_SESSION_YOLO") == "1" or is_yolo_active()


# -- Pre-exec guard helper (H23 partial) --------------------------

def container_can_skip_guards() -> bool:
    """True when running in container AND no host bind-mounts present.

    Hermes-Verbatim: Docker sandbox with host bind-mounts disables this
    fast-path (host file system is exposed).
    """
    if not is_container_context():
        return False
    # Check for bind-mount manifest / docker socket / etc.
    if os.environ.get("EACCODE_HOST_PATH_BIND") == "1":
        return False
    return True
