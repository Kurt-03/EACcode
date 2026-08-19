"""Workspace-isolation for eaccode (Plan H.minimal v3, Stufe 1).

The workspace is the only filesystem region eaccode's tools can read
or write. Default workspace = ``<cwd>/.eaccode-workspace/``.

Every path the model passes through a tool (read_file, write_file,
list_files, etc.) goes through ``rewrite_path`` and ``validate_path``.
Absolute paths outside the workspace are rejected. Path-traversal
(``..``) is rejected. Symlinks that would escape the workspace are
rejected (after ``Path.resolve(strict=False)``).

Memory and Skill paths are *not* sandboxed (cross-session persistent).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Names that must never be sandboxed - they live outside the cwd workspace
# and need cross-session persistence.
EXEMPT_PATH_FRAGMENTS = (
    "MEMORY.md",
    "USER.md",
    "/skills/",
    "\\skills\\",
    ".telegram-bot-config",
)


# Scope validation
_VALID_SCOPES = frozenset({"once", "session", "always"})


@dataclass(frozen=True)
class PathRule:
    """A single allow/deny rule attached to a workspace."""

    raw: str
    scope: str  # "once" | "session" | "always"
    kind: str   # "allow" | "deny"

    def __post_init__(self) -> None:
        if self.scope not in _VALID_SCOPES:
            raise ValueError(
                f"invalid scope {self.scope!r} (expected one of {sorted(_VALID_SCOPES)})"
            )
        if self.kind not in {"allow", "deny"}:
            raise ValueError(
                f"invalid kind {self.kind!r} (expected 'allow' or 'deny')"
            )


@dataclass
class WorkspaceError(ValueError):
    """Raised when a path violates workspace rules."""

    code: str  # e.g. "absolute_outside_workspace", "path_traversal", "symlink_escape"
    path: str
    workspace: str

    def __str__(self) -> str:
        return (
            f"workspace violation ({self.code}): {self.path!r} is outside "
            f"workspace {self.workspace!r}"
        )


@dataclass
class Workspace:
    """One workspace - root path + rules.

    Allow/Deny paths can be added at runtime via add_allow/add_deny.
    Patterns can use glob (``*``, ``?``) and are expanded with
    :class:`fnmatch.fnmatch` against the resolved target path.
    """

    root: Path
    allow_paths: list[Path] = field(default_factory=list)
    deny_paths: list[Path] = field(default_factory=list)
    # Rule stores (used by permissions-scope tracking)
    _allow_rules: list["PathRule"] = field(default_factory=list)
    _deny_rules: list["PathRule"] = field(default_factory=list)

    @property
    def root_str(self) -> str:
        return str(self.root)

    def add_allow(
        self,
        raw_path: str | Path,
        scope: str = "session",
    ) -> "PathRule":
        """Add a runtime allow-rule. Returns the new :class:`PathRule`."""
        rule = PathRule(raw=str(raw_path), scope=scope, kind="allow")
        self._allow_rules.append(rule)
        try:
            self.allow_paths.append(Path(raw_path).expanduser().resolve())
        except OSError:
            pass
        return rule

    def add_deny(
        self,
        raw_path: str | Path,
        scope: str = "always",
    ) -> "PathRule":
        """Add a runtime deny-rule. Returns the new :class:`PathRule`."""
        rule = PathRule(raw=str(raw_path), scope=scope, kind="deny")
        self._deny_rules.append(rule)
        try:
            self.deny_paths.append(Path(raw_path).expanduser().resolve())
        except OSError:
            pass
        return rule

    def list_rules(self) -> list["PathRule"]:
        """Return all registered rules (allow + deny)."""
        return self._allow_rules + self._deny_rules

    def remove_rule(self, rule: "PathRule") -> None:
        """Remove one specific rule by identity."""
        if rule in self._allow_rules:
            self._allow_rules.remove(rule)
        if rule in self._deny_rules:
            self._deny_rules.remove(rule)

    def is_exempt(self, path_str: str) -> bool:
        """True when this path bypasses the sandbox (memory/skills/etc)."""
        s = str(path_str)
        return any(frag in s for frag in EXEMPT_PATH_FRAGMENTS)

    def is_allowed_outside(self, path: Path) -> bool:
        """True when the path is in ``allow_paths``."""
        try:
            resolved = path.resolve()
        except OSError:
            return False
        for allowed in self.allow_paths:
            try:
                resolved.relative_to(allowed.resolve())
                return True
            except ValueError:
                continue
        return False

    def is_denied(self, path: Path) -> bool:
        """True when the path is in ``deny_paths``."""
        try:
            resolved = path.resolve()
        except OSError:
            return False
        for denied in self.deny_paths:
            try:
                resolved.relative_to(denied.resolve())
                return True
            except ValueError:
                continue
        return False

    def is_within(self, path: Path) -> bool:
        """True when ``path`` resolves inside ``root``."""
        try:
            resolved = path.resolve(strict=False)
        except OSError:
            return False
        try:
            resolved.relative_to(self.root.resolve())
            return True
        except ValueError:
            return False


def get_default_workspace() -> Workspace:
    """Build a Workspace rooted at ``Path.cwd()``.

    The current working directory IS the workspace. eaccode does NOT
    create a separate sub-directory - that would confuse users
    (``cd test1`` would mean workspace=test1, not test1/.eaccode-workspace/).
    """
    return Workspace(root=Path.cwd().resolve())


def load_workspace_from_config(config: Optional[dict] = None) -> Workspace:
    """Read the workspace root from config (or fall back to default)."""
    if config is None:
        try:
            from eaccode import config as cfg

            config = cfg.load_config() or {}
        except Exception:
            config = {}

    ws_cfg = (config or {}).get("workspace") or {}
    root_str = ws_cfg.get("root")
    if root_str:
        root = Path(root_str).expanduser().resolve()
    else:
        root = Path.cwd().resolve()

    allow_paths: list[Path] = []
    for raw in ws_cfg.get("allow_paths") or []:
        try:
            allow_paths.append(Path(raw).expanduser().resolve())
        except OSError:
            pass
    deny_paths: list[Path] = []
    for raw in ws_cfg.get("deny_paths") or []:
        try:
            deny_paths.append(Path(raw).expanduser().resolve())
        except OSError:
            pass

    return Workspace(root=root, allow_paths=allow_paths, deny_paths=deny_paths)


def rewrite_path(path_str: str, workspace: Workspace) -> Path:
    """Rewrite ``path_str`` into a workspace-bounded Path.

    Rules:
      - Empty string or ``.`` returns ``workspace.root``
      - ``~`` and ``~/...`` map to workspace root (NOT to the real home)
      - Relative paths (``foo``, ``./foo``, ``../foo``) resolve against
        the workspace root. ``..``-traversal that escapes the workspace
        raises ``WorkspaceError``.
      - Absolute paths outside the workspace raise
        ``WorkspaceError`` (unless explicitly allowed).
      - Exempt paths (MEMORY.md, USER.md, /skills/) are returned as-is.
      - Symlinks are resolved via ``Path.resolve(strict=False)``. If the
        resolved target escapes the workspace, raise ``WorkspaceError``.
      - Blocked devices (NUL, CON, /dev/null) raise
        ``WorkspaceError`` with code ``blocked_device``.
      - UNC paths (``\\\\server\\share``) raise ``WorkspaceError``.
    """
    if workspace.is_exempt(path_str):
        return Path(path_str).expanduser()

    if not path_str or path_str == ".":
        return workspace.root

    # Tilde expansion - redirect into workspace, NOT real home.
    if path_str.startswith("~"):
        home = Path.home()
        if path_str == "~":
            return workspace.root
        if path_str.startswith("~/") or path_str.startswith("~\\"):
            rel = path_str[2:]
            return (workspace.root / rel).resolve(strict=False)
        return workspace.root  # ``~user/foo`` falls through to workspace root

    # Blocked-device detection (before any resolution)
    from eaccode.path_security import is_blocked_device, is_unc_path

    if is_unc_path(path_str):
        raise WorkspaceError(
            code="unc_path", path=path_str, workspace=workspace.root_str
        )
    if is_blocked_device(path_str):
        raise WorkspaceError(
            code="blocked_device", path=path_str, workspace=workspace.root_str
        )

    p = Path(path_str)

    # If absolute, validate it.
    if p.is_absolute() or path_str.startswith(("/", "\\")):
        try:
            resolved = p.resolve(strict=False)
        except OSError as exc:
            raise WorkspaceError(
                code="path_unresolvable", path=str(p), workspace=workspace.root_str
            ) from exc
        if workspace.is_denied(resolved):
            raise WorkspaceError(
                code="explicitly_denied", path=str(p), workspace=workspace.root_str
            )
        if not workspace.is_within(resolved) and not workspace.is_allowed_outside(resolved):
            raise WorkspaceError(
                code="absolute_outside_workspace",
                path=str(p),
                workspace=workspace.root_str,
            )
        return resolved

    # Relative path - resolve against workspace.root, NOT caller cwd.
    candidate = (workspace.root / path_str).resolve(strict=False)

    # Path-traversal: ensure resolved is still within root.
    try:
        candidate.relative_to(workspace.root.resolve())
    except ValueError as exc:
        raise WorkspaceError(
            code="path_traversal",
            path=str(p),
            workspace=workspace.root_str,
        ) from exc

    # Symlink-escape: resolve and re-check.
    if workspace.is_denied(candidate):
        raise WorkspaceError(
            code="explicitly_denied", path=str(candidate), workspace=workspace.root_str
        )
    if not workspace.is_within(candidate) and not workspace.is_allowed_outside(candidate):
        raise WorkspaceError(
            code="symlink_escape",
            path=str(candidate),
            workspace=workspace.root_str,
        )
    return candidate


def is_path_safe_for_workspace(path: Path, workspace: Workspace) -> bool:
    """True when ``path`` resolves inside the workspace."""
    try:
        path.relative_to(workspace.root.resolve())
        return True
    except ValueError:
        return False


# Session-scoped state dicts (Hermes _authoritative_workspace_root analog).
# All state is keyed by ``session_key`` so concurrent sessions don't
# collide. Tests that don't care about isolation can pass the default
# key (None) and behaviour matches the legacy module-global layout.
import threading as _threading

_active_workspaces: dict[str, "Workspace"] = {}
_session_cwds: dict[str, "Path"] = {}
_session_lock = _threading.RLock()

DEFAULT_SESSION_KEY = "default"


def _key(session_key: "str | None") -> str:
    """Resolve a session_key to the dict lookup key."""
    return str(session_key or DEFAULT_SESSION_KEY)


def get_active_workspace(session_key: "str | None" = None) -> "Workspace":
    """Return the active workspace for ``session_key``.

    Lazily initialises the default one. Workspace root follows the
    session cwd when one has been recorded (Hermes-style authoritative
    root). Otherwise falls back to ``Path.cwd()`` at first call.
    """
    key = _key(session_key)
    with _session_lock:
        ws = _active_workspaces.get(key)
        if ws is None:
            cwd = _session_cwds.get(key) or Path.cwd()
            ws = Workspace(root=cwd.resolve())
            _active_workspaces[key] = ws
        return ws


def set_active_workspace(ws_obj: "Workspace", session_key: "str | None" = None) -> None:
    """Override the active workspace for ``session_key`` (tests, runtime config)."""
    key = _key(session_key)
    with _session_lock:
        _active_workspaces[key] = ws_obj


def update_session_cwd(
    new_cwd: "str | Path",
    session_key: "str | None" = None,
) -> None:
    """Re-anchor the active workspace to ``new_cwd`` for ``session_key``.

    Thread-safe: all reads/writes are guarded by ``_session_lock``.
    """
    key = _key(session_key)
    resolved = Path(new_cwd).expanduser().resolve()
    with _session_lock:
        _session_cwds[key] = resolved
        existing = _active_workspaces.get(key)
        if existing is not None:
            existing.root = resolved
        else:
            _active_workspaces[key] = Workspace(root=resolved)


def get_session_cwd(session_key: "str | None" = None) -> "Path | None":
    """Return the recorded cwd for ``session_key``, or None when unset."""
    key = _key(session_key)
    with _session_lock:
        return _session_cwds.get(key)


def clear_session_state(session_key: "str | None" = None) -> None:
    """Drop the workspace + cwd record for ``session_key`` (teardown)."""
    key = _key(session_key)
    with _session_lock:
        _active_workspaces.pop(key, None)
        _session_cwds.pop(key, None)


# Alias used by /approvals - the underscore prefix is intentional so the
# command module can grab it without colliding with the public name.
_get_active_workspace = get_active_workspace


def expand_tilde(path_str: str) -> str:
    """Hermes-style ``~`` and ``~/foo`` expansion.

    Returns ``path_str`` unchanged when it doesn't start with ``~``.
    On Windows, ``~`` resolves to the user's home directory.
    """
    if not path_str.startswith("~"):
        return path_str
    home = Path.home()
    if path_str == "~":
        return str(home)
    if path_str.startswith("~/"):
        return str(home / path_str[2:])
    if path_str.startswith("~\\"):
        return str(home / path_str[2:])
    return path_str


# Alias used by /approvals - the underscore prefix is intentional so the
# command module can grab it without colliding with the public name.
_get_active_workspace = get_active_workspace


# Hermes has ``_search_result_read_block_error`` + ``_filter_read_blocked_search_results``.
# We mirror them so search results don't leak blocked paths back to the model.
_SEARCH_BLOCK_PREFIXES = (
    ".ssh",
    ".aws",
    ".gnupg",
    ".kube",
    ".docker",
    ".netrc",
    ".pgpass",
    ".npmrc",
    ".pypirc",
    ".git-credentials",
    ".anthropic_oauth.json",
)


def is_search_blocked_path(path: "Path | str") -> bool:
    """True when ``path`` is a sensitive directory prefix (Hermes-style)."""
    s = str(path).replace("\\", "/")
    parts = s.split("/")
    return any(p in _SEARCH_BLOCK_PREFIXES for p in parts)


def filter_search_results(results: list[str], workspace: "Workspace") -> list[str]:
    """Filter ``results`` so blocked paths are not leaked back to the model.

    Returns the filtered list. Each entry is a ``path:line:text`` triple
    (the format search_files emits). Entries whose path falls under
    ``_SEARCH_BLOCK_PREFIXES`` are replaced with a sentinel so the model
    still sees the count but not the content.
    """
    filtered: list[str] = []
    blocked_count = 0
    for entry in results:
        # path is the first : - separated segment
        path_part = entry.split(":", 1)[0] if ":" in entry else entry
        if is_search_blocked_path(path_part) and not workspace.is_allowed_outside(Path(path_part)):
            blocked_count += 1
            continue
        filtered.append(entry)
    if blocked_count:
        filtered.append(f"(filtered {blocked_count} matches in sensitive directories)")
    return filtered


__all__ = [
    "Workspace",
    "WorkspaceError",
    "EXEMPT_PATH_FRAGMENTS",
    "PathRule",
    "get_default_workspace",
    "get_active_workspace",
    "set_active_workspace",
    "update_session_cwd",
    "get_session_cwd",
    "expand_tilde",
    "load_workspace_from_config",
    "rewrite_path",
    "is_path_safe_for_workspace",
    "is_search_blocked_path",
    "filter_search_results",
]
