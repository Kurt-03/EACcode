"""Built-in tools for the agent (Phase A5).

Every tool returns a plain string: the result, or an "Error: ..." message.
Tools never raise — the agent loop stays alive.
"""

from __future__ import annotations

import platform
import re
import subprocess
import threading
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from eaccode.agent import Tool

# Module-level permission handler. Tools that need user confirmation
# look this up by name (no run_command in this build; reserved for future).

READ_CHARS = 8000
FETCH_CHARS = 8000
SEARCH_RESULTS = 5

# Module-level workspace for tool-path rewriting. Initialised lazily;
# tests that need a different workspace can monkey-patch this attribute.
_workspace = None


def _get_workspace():
    """Return the module workspace, loading from config on first call."""
    global _workspace
    if _workspace is None:
        from eaccode.workspace import load_workspace_from_config
        _workspace = load_workspace_from_config()
    return _workspace


def _set_workspace(ws_obj) -> None:
    """Override the workspace (used by tests)."""
    global _workspace
    _workspace = ws_obj

# Safe default permission handler.


def _deny_permission(command: str) -> bool:
    return False


# Thread-local flag set by the agent loop. When a tool wants to skip its
# own prompt (because the loop already decided), it sets this to True.
_loop_permission_checked = threading.local()


def set_loop_permission_checked(value: bool) -> None:
    """Set the thread-local flag (Plan K fix: public so cli.py can call it)."""
    _loop_permission_checked.value = value

# Backward-compat alias
_set_loop_permission_checked = set_loop_permission_checked


permission_handler: Callable[[str], bool] = _deny_permission


def read_file(
    path: str,
    max_chars: int = READ_CHARS,
    offset: int = 0,
    limit: int | None = None,
) -> str:
    """Read a text file, optionally paged with ``offset`` / ``limit``.

    - ``offset``: skip the first N lines before reading.
    - ``limit``: stop after N lines.
    - ``max_chars``: hard cap on total characters returned.

    Use this for large files: read offset/limit segments instead of
    blowing the context window.

    **Truncation safety**: when content is truncated, the result
    begins with an explicit marker so callers (especially ``file_edit``)
    can detect that the returned text is incomplete. NEVER pass a
    truncated chunk as ``old_string`` to ``file_edit`` - use
    ``repo_search`` first to find the exact line numbers, then read
    the precise offset/limit window.
    """
    from eaccode.workspace import WorkspaceError, rewrite_path

    try:
        target = rewrite_path(path, _get_workspace())
    except WorkspaceError as exc:
        return f"Error: {exc}"
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Error: cannot read {target}: {exc}"

    lines = text.splitlines(keepends=True)
    total_lines = len(lines)
    start = max(0, offset)
    end = start + limit if limit is not None else total_lines
    paged = "".join(lines[start:end])

    truncated = False
    if len(paged) > max_chars:
        paged = paged[:max_chars]
        truncated = True

    if truncated:
        # CRITICAL: tell the model the result is incomplete so it
        # does NOT pass this chunk to file_edit as old_string.
        return (
            f"--- WARNING: CONTENT TRUNCATED ---\n"
            f"This file is {total_lines} lines total. "
            f"You asked for offset={offset}, limit={limit}. "
            f"Only the first {max_chars} chars are shown.\n"
            f"DO NOT use this truncated text as old_string in file_edit! "
            f"Re-read with explicit offset/limit that covers your target.\n"
            f"--- BEGIN TRUNCATED CONTENT ---\n"
            f"{paged}\n"
            f"--- END (truncated) ---"
        )
    return paged


def write_file(path: str, content: str) -> str:
    """Write text to a file, creating parent directories."""
    from eaccode.workspace import WorkspaceError, rewrite_path

    try:
        target = rewrite_path(path, _get_workspace())
    except WorkspaceError as exc:
        return f"Error: {exc}"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"Error: cannot write {target}: {exc}"
    return f"written {len(content)} chars to {target}"


def list_files(path: str = ".") -> str:
    """List directory entries (directories get a trailing slash)."""
    from eaccode.workspace import WorkspaceError, rewrite_path

    try:
        target = rewrite_path(path, _get_workspace())
    except WorkspaceError as exc:
        return f"Error: {exc}"
    try:
        entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        return f"Error: cannot list {target}: {exc}"
    lines = [f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries]
    return "\n".join(lines) or "(empty)"


def search_files(
    pattern: str,
    path: str = ".",
    file_types: str | None = None,
    use_regex: bool = True,
    max_results: int = 200,
) -> str:
    """Search ``path`` for ``pattern`` using ripgrep (or Python fallback).

    Args:
        pattern: Regex by default; set ``use_regex=False`` for literal text.
        path: Workspace-relative path (default: workspace root).
        file_types: Optional glob like ``"*.py"`` to restrict file types.
        max_results: Cap on number of matches returned (default 200).

    Output format: ``path:line:text`` (matches ripgrep's ``--line-number``).
    """
    import shutil as _sh
    import subprocess as _sp

    from eaccode.workspace import WorkspaceError, rewrite_path

    try:
        root = rewrite_path(path, _get_workspace())
    except WorkspaceError as exc:
        return f"Error: {exc}"

    if _sh.which("rg"):
        cmd = ["rg", "--no-heading", "--line-number", "--hidden"]
        if not use_regex:
            cmd.append("--fixed-strings")
        if file_types:
            cmd.extend(["-g", file_types])
        cmd.extend([pattern, str(root)])
        try:
            result = _sp.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode in (0, 1):
                lines = result.stdout.splitlines()[:max_results]
                return "\n".join(lines) or "no matches"
        except (_sp.TimeoutExpired, OSError):
            pass  # fall through

    # Python fallback (literal substring search).
    matches: list[str] = []
    needle = pattern
    try:
        for candidate in root.rglob("*"):
            if not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if pattern in text:
                matches.append(str(candidate))
                if len(matches) >= 50:
                    break
    except OSError as exc:
        return f"Error: {exc}"
    return "\n".join(matches) or "no matches"


def http_get(url: str, max_chars: int = FETCH_CHARS) -> str:
    """Fetch a URL and return its text content."""
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = response.read(max_chars + 512).decode("utf-8", errors="replace")
    except Exception as exc:
        return f"Error: cannot fetch {url}: {exc}"
    return data[:max_chars]


def web_search(query: str, max_results: int = SEARCH_RESULTS) -> str:
    """Search the web via DuckDuckGo HTML; returns title + url per hit."""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            html = response.read(200_000).decode("utf-8", errors="replace")
    except Exception as exc:
        return f"Error: search failed: {exc}"
    lines: list[str] = []
    for match in re.finditer(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S
    ):
        url_href, title = match.group(1), re.sub(r"<[^>]+>", "", match.group(2))
        title = title.strip()
        if title:
            lines.append(f"{title}\n  {url_href}")
        if len(lines) >= max_results:
            break
    return "\n".join(lines) or "(no results)"


def current_time() -> str:
    """Current local date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def system_info() -> str:
    """Operating system and hardware summary."""
    return f"{platform.system()} {platform.release()} - {platform.machine()}"


def run_command(command: str, cwd: str | None = None, timeout: int = 60) -> str:
    """Run a shell command; gated by the permission handler.

    When ``EACCODE_RUN_IN_CONTAINER=1`` and Docker is available, the
    command runs inside a fresh container instead of the host shell.
    """
    import os as _os
    from eaccode.workspace import WorkspaceError, rewrite_path

    target_cwd_str = cwd or str(_get_workspace().root)
    try:
        target_cwd = rewrite_path(target_cwd_str, _get_workspace())
    except WorkspaceError as exc:
        return f"Error: {exc}"
    target_cwd = str(target_cwd)

    is_container = _os.environ.get("EACCODE_RUN_IN_CONTAINER") == "1"

    # Permission gate (skipped when loop already approved).
    if not getattr(_loop_permission_checked, "value", False):
        if not permission_handler(command):
            return f"Error: permission denied for: {command[:80]}"

    if is_container:
        try:
            from eaccode.container import (
                is_docker_available,
                start_container,
                exec_in_container,
                stop_container,
                ContainerConfig,
            )
        except ImportError:
            return "Error: container module unavailable"
        if not is_docker_available():
            return "Error: EACCODE_RUN_IN_CONTAINER=1 but docker not available"
        try:
            cfg = ContainerConfig(workspace=Path(target_cwd))
            handle = start_container(cfg)
        except (RuntimeError, OSError) as exc:
            return f"Error: container start failed: {exc}"
        try:
            code, output = exec_in_container(handle, ["sh", "-c", command])
        except OSError as exc:
            stop_container(handle)
            return f"Error: container exec failed: {exc}"
        finally:
            stop_container(handle)
        output = (output or "").strip()
        if code != 0:
            output = f"{output}\n(exit {code})"
        return output or "(no output)"

    # Native execution.
    import subprocess as _sp
    try:
        result = _sp.run(
            command,
            shell=True,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except _sp.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except OSError as exc:
        return f"Error: {exc}"
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        output = f"{output}\n(exit {result.returncode})"
    return output or "(no output)"


BUILTIN_TOOLS: list[Tool] = [
    Tool(
        "read_file",
        "Read a text file. Returns the file content as a plain string, "
        "truncated to 8000 chars. Returns 'Error: file not readable: <path>' "
        "when the file is missing, binary, or the path is a directory.",
        read_file,
        {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Absolute or relative file path. Supports text files "
                        "(utf-8, latin-1, ascii); binary files return an "
                        "Error string."
                    ),
                },
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "Truncate the output after this many chars "
                        "(default: 8000). Use a smaller value to preview "
                        "large files."
                    ),
                },
            },
            "required": ["path"],
        },
        mutates=False,
    ),
    Tool(
        "write_file",
        "Write text to a file, creating parent directories if missing. "
        "Returns 'wrote <path>' on success, or 'Error: ...' on permission "
        "denied, invalid path, or parent-dir creation failure. "
        "Sensitive paths (.ssh/, .env, config.yaml) trigger a Smart-mode "
        "review and an approval prompt.",
        write_file,
        {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Absolute or relative path. Parent directories are "
                        "created automatically. Overwrites the file if it "
                        "exists."
                    ),
                },
                "content": {
                    "type": "string",
                    "description": (
                        "UTF-8 text to write to the file. For multi-line "
                        "content use \n in JSON-encoding contexts."
                    ),
                },
            },
            "required": ["path", "content"],
        },
        mutates=True,
    ),
    Tool(
        "list_files",
        "List directory entries (name + type marker + size). "
        "Returns lines of 'name\tdescription' (file/dir marker, size "
        "in bytes for files). Empty string when the directory is empty. "
        "Returns 'Error: ...' when the path is missing.",
        list_files,
        {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Directory path (default: current working "
                        "directory)."
                    ),
                },
            },
        },
        mutates=False,
    ),
    Tool(
        "search_files",
        "Find files whose text contains a regex pattern via ripgrep. "
        "Returns 'path:line: <matched line>' per match, or '(no matches)' "
        "when nothing is found. Returns 'Error: ...' when ripgrep is not "
        "installed or the path is missing.",
        search_files,
        {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": (
                        "regex pattern. Use Python regex syntax (groups, "
                        "look-aheads, anchors)."
                    ),
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Root directory to search (default: current "
                        "working directory)."
                    ),
                },
            },
            "required": ["pattern"],
        },
        mutates=False,
    ),
    Tool(
        "run_command",
        "Run a shell command via subprocess.run(shell=True). "
        "Returns stdout+stderr combined plus '(exit N)' on non-zero exit. "
        "Returns 'Error: permission denied ...' when blocked, "
        "'Error: command timed out after Ns' on timeout, or "
        "'Error: <OSError>' on missing binary / OS issues. "
        "POLICY: Smart-mode routes dangerous commands (rm -rf, chmod 777, "
        "curl|sh) through an Aux-LLM reviewer; Hardline patterns "
        "(rm -rf /, sudo -S, shutdown, fork bombs) always block. "
        "Set EACCODE_RUN_IN_CONTAINER=1 to run inside a Docker container.",
        run_command,
        {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "Shell command string. Evaluated via /bin/sh on "
                        "POSIX or cmd.exe on Windows."
                    ),
                },
                "cwd": {
                    "type": "string",
                    "description": (
                        "Working directory for the subprocess "
                        "(default: workspace root)."
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        "Subprocess timeout in seconds (default: 60). "
                        "Returns 'Error: command timed out after Ns' "
                        "on expiry."
                    ),
                },
            },
            "required": ["command"],
        },
        mutates=True,
        always_ask=True,
    ),
    Tool(
        "http_get",
        "Fetch a URL via urllib and return the text content "
        "(first 8000 chars by default). Returns 'Error: cannot fetch "
        "<url>: <reason>' on network / 4xx / 5xx failures.",
        http_get,
        {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "Full URL including scheme (http or https). "
                        "Domains in allowlist-fetch are unrestricted; "
                        "others may be filtered."
                    ),
                },
                "max_chars": {
                    "type": "integer",
                    "description": (
                        "Truncate the response body after this many chars "
                        "(default: 8000)."
                    ),
                },
            },
            "required": ["url"],
        },
        mutates=False,
    ),
    Tool(
        "web_search",
        "Search the web via DuckDuckGo HTML. Returns title + url lines "
        "(up to max_results). Returns '(no results)' or "
        "'Error: search failed: <reason>' on DuckDuckGo rate-limit.",
        web_search,
        {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Free-text search query. Use quotes for "
                        "exact-phrase matching."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": (
                        "Maximum number of result titles to return "
                        "(default: 5)."
                    ),
                },
            },
            "required": ["query"],
        },
        mutates=False,
    ),
    Tool(
        "current_time",
        "Current local date+time. Returns ISO-style "
        "'YYYY-MM-DD HH:MM:SS' in local timezone (system default).",
        current_time,
        mutates=False,
    ),
    Tool(
        "system_info",
        "Operating system and hardware summary. Returns one line: "
        "'<System> <Release> - <Machine>' (e.g. 'Windows 11 - AMD64').",
        system_info,
        mutates=False,
    ),
]



def sorted_for_manifest(tools: list[Tool] | None = None) -> list[Tool]:
    """Plan L L.4: sort tools so read-only come first in the manifest.

    Model is more likely to pick the right tool when read-only tools
    (high use, low risk) appear before mutating tools in the list.
    Order:
      1. read-only (sort by name)
      2. mutating (sort by name)
    """
    tools = tools if tools is not None else BUILTIN_TOOLS
    readonly = sorted((t for t in tools if not t.mutates), key=lambda t: t.name)
    mutating = sorted((t for t in tools if t.mutates), key=lambda t: t.name)
    return readonly + mutating
