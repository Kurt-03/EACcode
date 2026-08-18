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
    """One workspace - root path + rules."""

    root: Path
    allow_paths: list[Path] = field(default_factory=list)
    deny_paths: list[Path] = field(default_factory=list)

    @property
    def root_str(self) -> str:
        return str(self.root)

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
      - ``~`` and ``~/...`` expand to workspace root
      - Relative paths (``foo``, ``./foo``, ``../foo``) resolve against
        the workspace root, *not* the caller's cwd. ``..``-traversal
        that would escape the workspace raises ``WorkspaceError``.
      - Absolute paths outside the workspace raise
        ``WorkspaceError`` (unless explicitly allowed).
      - Exempt paths (MEMORY.md, USER.md, /skills/, .telegram-bot-config)
        are returned as-is.
      - Symlinks are resolved via ``Path.resolve(strict=False)``. If the
        resolved target escapes the workspace, raise ``WorkspaceError``.
    """
    if workspace.is_exempt(path_str):
        return Path(path_str).expanduser()

    if not path_str or path_str == ".":
        return workspace.root

    # Tilde expansion - inside the workspace.
    if path_str.startswith("~"):
        path_str = str(Path(path_str).expanduser())
        # If user passed an absolute home path, redirect into workspace.
        if os.path.isabs(path_str):
            rel = Path(path_str).relative_to(Path.home()) if path_str.startswith(str(Path.home())) else Path(path_str).name
            return (workspace.root / rel).resolve(strict=False)

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


__all__ = [
    "Workspace",
    "WorkspaceError",
    "EXEMPT_PATH_FRAGMENTS",
    "get_default_workspace",
    "load_workspace_from_config",
    "rewrite_path",
    "is_path_safe_for_workspace",
]
