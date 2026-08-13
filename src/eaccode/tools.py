"""Built-in tools for the agent (Phase A5).

Every tool returns a plain string: the result, or an "Error: ..." message.
Tools never raise — the agent loop stays alive.
"""

from __future__ import annotations

import platform
import re
import subprocess
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from eaccode.agent import Tool

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
    if not permission_handler(command):
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
        output = f"{output}\n(exit {result.returncode})".strip()
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
        "Read a text file (truncated to 8000 chars).",
        read_file,
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "max_chars": {"type": "integer"}},
            "required": ["path"],
        },
    ),
    Tool(
        "write_file",
        "Write text to a file, creating parent directories.",
        write_file,
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    ),
    Tool(
        "list_files",
        "List directory entries.",
        list_files,
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
        },
    ),
    Tool(
        "search_files",
        "Find files whose text contains a pattern.",
        search_files,
        {
            "type": "object",
            "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}},
            "required": ["pattern"],
        },
    ),
    Tool(
        "run_command",
        "Run a shell command (requires user permission).",
        run_command,
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "cwd": {"type": "string"},
                "timeout": {"type": "integer"},
            },
            "required": ["command"],
        },
    ),
    Tool(
        "http_get",
        "Fetch a URL and return its text content.",
        http_get,
        {
            "type": "object",
            "properties": {"url": {"type": "string"}, "max_chars": {"type": "integer"}},
            "required": ["url"],
        },
    ),
    Tool(
        "web_search",
        "Search the web via DuckDuckGo; returns titles and urls.",
        web_search,
        {
            "type": "object",
            "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}},
            "required": ["query"],
        },
    ),
    Tool("current_time", "Current local date and time.", current_time),
    Tool("system_info", "Operating system and hardware summary.", system_info),
]
