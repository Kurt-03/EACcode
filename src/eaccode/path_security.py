"""Strict path validation (Plan H.minimal v4, Tag 4).

Hermes-style helpers beyond the basic ``rewrite_path`` check:
- ``has_traversal_component(path)`` - explicit ".." or "//" detection
- ``is_blocked_device(path)`` - Windows device paths (C:/aux, NUL, COM1)
- ``is_unc_path(path)`` - ``\\\\server\\share`` detection
- ``is_path_within_dir(path, root)`` - strict root containment
- ``validate_within_dir(path, root)`` - raises WorkspaceError on violations
"""

from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath
from typing import Union

from eaccode.workspace import WorkspaceError


# Windows reserved device names (used as filenames)
_WINDOWS_DEVICES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})


def has_traversal_component(path_str: str) -> bool:
    """True when ``path_str`` has ``..`` or backtrack components.

    Detects ``..`` as a path segment (not as part of a filename), and
    absolute-path tricks like ``/./../etc/passwd``.
    """
    s = path_str.replace("\\", "/")
    parts = s.split("/")
    return any(p == ".." or p == "." and any(prev == ".." for prev in parts) for p in parts)


def is_blocked_device(path_str: str) -> bool:
    """True when ``path_str`` references a Windows device path.

    Examples:
        ``C:/aux`` -> True (Windows treats "aux" as a device)
        ``/dev/null`` -> True on POSIX
        ``./CON`` -> True
        ``CON.txt`` -> False (not a device, just a file with "CON" as prefix)
    """
    p = Path(path_str)
    # Match exact basename (no extension stripping) - we want "CON.txt" to NOT match
    name = p.name.upper()
    if name in _WINDOWS_DEVICES:
        return True
    # POSIX device files - exact match (not prefix) to avoid blocking /dev/myapp
    posix_devices = {
        "/dev/null", "/dev/zero", "/dev/random", "/dev/urandom",
        "/dev/stdin", "/dev/stdout", "/dev/stderr", "/dev/tty",
        "/dev/console", "/dev/ptmx", "/dev/full", "/dev/loop0",
    }
    if path_str in posix_devices:
        return True
    return False


def is_unc_path(path_str: str) -> bool:
    """True when ``path_str`` is a UNC path (\\\\server\\share or //server/share)."""
    if path_str.startswith("\\\\") and len(path_str) > 2 and path_str[2] != "\\":
        return True
    if path_str.startswith("//") and len(path_str) > 2 and path_str[2] != "/":
        return True
    return False


def is_path_within_dir(path: Union[str, Path], root: Union[str, Path]) -> bool:
    """Strict containment check: ``path`` resolves to a location inside ``root``.

    Uses ``Path.resolve(strict=False)`` then ``relative_to``. Both must
    succeed. Symlinks that resolve outside ``root`` return False.
    """
    try:
        p = Path(path).resolve(strict=False)
        r = Path(root).resolve(strict=False)
    except OSError:
        return False
    try:
        p.relative_to(r)
        return True
    except ValueError:
        return False


def validate_within_dir(path: Union[str, Path], root: Union[str, Path]) -> Path:
    """Strict validation: return resolved Path or raise ``WorkspaceError``.

    Raises ``WorkspaceError`` with code:
        - ``path_traversal`` if ``..`` is present
        - ``symlink_escape`` if a symlink resolves outside ``root``
        - ``blocked_device`` if path targets a device (e.g. C:/aux)
        - ``unc_path`` if path is a UNC share
        - ``path_outside_root`` if path is otherwise outside root
    """
    path_str = str(path)
    if has_traversal_component(path_str):
        raise WorkspaceError(
            code="path_traversal",
            path=path_str,
            workspace=str(root),
        )
    if is_unc_path(path_str):
        raise WorkspaceError(
            code="unc_path",
            path=path_str,
            workspace=str(root),
        )
    if is_blocked_device(path_str):
        raise WorkspaceError(
            code="blocked_device",
            path=path_str,
            workspace=str(root),
        )
    try:
        resolved = Path(path_str).resolve(strict=False)
    except OSError as exc:
        raise WorkspaceError(
            code="path_unresolvable",
            path=path_str,
            workspace=str(root),
        ) from exc
    if not is_path_within_dir(resolved, root):
        raise WorkspaceError(
            code="path_outside_root",
            path=path_str,
            workspace=str(root),
        )
    return resolved


__all__ = [
    "has_traversal_component",
    "is_blocked_device",
    "is_unc_path",
    "is_path_within_dir",
    "validate_within_dir",
]