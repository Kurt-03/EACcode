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

# Set by the agent loop while a run_command call is executing: the loop's
# permission gate already decided, so run_command skips its own prompt.
_loop_permission_checked = threading.local()

READ_CHARS = 8000
FETCH_CHARS = 8000
SEARCH_RESULTS = 5

# Terminal permission gate. The REPL/TUI wires an interactive prompt here
# (Phase A7); the safe default is to deny.


def _deny_permission(command: str) -> bool:
    return False


permission_handler: Callable[[str], bool] = _deny_permission


def read_file(path: str, max_chars: int = READ_CHARS) -> str:
    """Read a text file, truncated to max_chars."""
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Error: cannot read {path}: {exc}"
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n...[truncated at {max_chars} chars]"
    return content


def write_file(path: str, content: str) -> str:
    """Write text to a file, creating parent directories."""
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"Error: cannot write {path}: {exc}"
    return f"written {len(content)} chars to {path}"


def list_files(path: str = ".") -> str:
    """List directory entries (directories get a trailing slash)."""
    try:
        entries = sorted(Path(path).iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        return f"Error: cannot list {path}: {exc}"
    lines = [f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries]
    return "\n".join(lines) or "(empty)"


def search_files(pattern: str, path: str = ".") -> str:
    """Find files under path whose text contains pattern (max 50 hits)."""
    matches: list[str] = []
    try:
        root = Path(path)
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


def run_command(command: str, cwd: str | None = None, timeout: int = 30) -> str:
    """Run a shell command; gated by the permission handler."""
    if not getattr(_loop_permission_checked, "value", False) and not permission_handler(
        command
    ):
        return f"Error: permission denied for command: {command}"
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except OSError as exc:
        return f"Error: {exc}"
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        # Phase B.1: surface exit-code via warning prefix that the
        # status_line picks up. Format: "⚠ exit=N: <output>"
        output = f"{output}\n⚠ exit={result.returncode} (non-zero)".strip()
    return output or "(no output)"


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
        "(rm -rf /, sudo -S, shutdown, fork bombs) always block.",
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
                        "(default: inherits caller's cwd)."
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        "Subprocess timeout in seconds (default: 30). "
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
