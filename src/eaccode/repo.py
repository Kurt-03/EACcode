"""Repo understanding (Phase D1): structure index, search, context packs.

The agent uses these tools to grasp a codebase before editing it:
- ``repo_scan``: tree-style index with .gitignore respect and size info
- ``repo_search``: recursive regex search with relative paths
- ``repo_context``: bundle a module with its related test files

All tools are read-only and run freely in ask mode.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eaccode.agent import Tool

MAX_FILES = 2000
MAX_DEPTH = 12
MAX_SEARCH_RESULTS = 50

# directories that are never indexed
ALWAYS_IGNORED = frozenset(
    {".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
)


@dataclass
class IgnoreRules:
    """Compiled .gitignore patterns (globs, dir-only, negation)."""

    patterns: list[tuple[re.Pattern[str], bool]] = field(default_factory=list)

    @classmethod
    def from_file(cls, gitignore: Path | None) -> IgnoreRules:
        rules = cls()
        if gitignore is None or not gitignore.exists():
            return rules
        for raw in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            pattern = line[1:] if negate else line
            if pattern.endswith("/"):
                pattern = pattern[:-1] + "/**"
            regex = glob_to_regex(pattern)
            rules.patterns.append((regex, negate))
        return rules

    def is_ignored(self, rel_path: str) -> bool:
        """True when the relative path matches ignore rules (negation wins)."""
        ignored = False
        for regex, negate in self.patterns:
            if regex.search(rel_path):
                ignored = not negate
        return ignored


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a gitignore-style glob into a regex (**, *, ?, [..])."""

    def core(part: str) -> str:
        translated = fnmatch.translate(part)
        # strip the (?s: ... )\Z wrapper (Python >=3.14 emits \z)
        if translated.startswith("(?s:") and (
            translated.endswith(")\\Z") or translated.endswith(")\\z")
        ):
            return translated[4:-3]
        return translated

    parts = pattern.split("/")
    regex_parts: list[str] = []
    for part in parts:
        if part == "**":
            # matches any number of segments INCLUDING the final file
            regex_parts.append("(?:[^/]+/)*[^/]*")
        else:
            regex_parts.append(core(part))
    body = "/".join(regex_parts)
    # patterns without '/' match basenames at any depth
    if "/" not in pattern:
        body = f"(?:[^/]*/)*{body}"
    return re.compile(body)


@dataclass
class RepoEntry:
    """One indexed file (relative path + size)."""

    path: str
    size: int


@dataclass
class RepoIndex:
    root: str
    entries: list[RepoEntry] = field(default_factory=list)
    truncated: bool = False

    @property
    def file_count(self) -> int:
        return len(self.entries)

    @property
    def total_size(self) -> int:
        return sum(entry.size for entry in self.entries)


def _walk(root: Path) -> list[tuple[Path, Path]]:
    """Yield (dir, file) pairs, respecting .gitignore and hard limits."""
    ignore_rules = IgnoreRules.from_file(root / ".gitignore")
    results: list[tuple[Path, Path]] = []
    for current, dirs, files in root.walk(top_down=True):
        depth = len(current.relative_to(root).parts)
        if depth > MAX_DEPTH:
            dirs[:] = []
            continue
        kept_dirs: list[str] = []
        for dirname in sorted(dirs):
            if dirname in ALWAYS_IGNORED:
                continue
            rel = current.relative_to(root).as_posix()
            candidate = f"{rel}/{dirname}" if rel != "." else dirname
            if not ignore_rules.is_ignored(candidate + "/"):
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs
        for filename in sorted(files):
            if len(results) >= MAX_FILES:
                return results
            rel = current.relative_to(root).as_posix()
            candidate = f"{rel}/{filename}" if rel != "." else filename
            if ignore_rules.is_ignored(candidate):
                continue
            results.append((current, Path(filename)))
    return results


def scan(root: str | Path = ".", max_files: int = MAX_FILES) -> RepoIndex:
    """Index a repository: files with sizes, .gitignore-respecting."""
    base = Path(root).expanduser().resolve()
    index = RepoIndex(root=str(base))
    if not base.exists() or not base.is_dir():
        return index
    for directory, file_path in _walk(base):
        if len(index.entries) >= max_files:
            index.truncated = True
            break
        try:
            size = (directory / file_path).stat().st_size
        except OSError:
            size = 0
        rel = (directory / file_path).relative_to(base).as_posix()
        index.entries.append(RepoEntry(path=rel, size=size))
    return index


def format_index(index: RepoIndex, limit: int = 150) -> str:
    """Render a compact tree-ish overview of the index."""
    if not index.entries:
        return f"(empty or missing directory: {index.root})"
    lines = [f"repo: {index.root}"]
    lines.append(f"files: {index.file_count}  total: {index.total_size} bytes")
    shown = index.entries[:limit]
    for entry in shown:
        lines.append(f"  {entry.path}  ({entry.size} B)")
    if index.truncated or len(index.entries) > limit:
        lines.append(f"  … {len(index.entries) - len(shown)} more (truncated)")
    return "\n".join(lines)


def search(
    root: str | Path = ".",
    pattern: str = "",
    file_types: list[str] | None = None,
    max_results: int = MAX_SEARCH_RESULTS,
) -> list[dict[str, Any]]:
    """Regex search over indexed files; returns {path, line, text} dicts."""
    base = Path(root).expanduser().resolve()
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return [{"path": "<error>", "line": 0, "text": f"invalid regex: {exc}"}]
    index = scan(base)
    hits: list[dict[str, Any]] = []
    for entry in index.entries:
        if file_types:
            suffix = Path(entry.path).suffix
            if suffix not in file_types and Path(entry.path).name not in file_types:
                continue
        try:
            lines = (base / entry.path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if regex.search(line):
                hits.append({"path": entry.path, "line": lineno, "text": line.strip()[:200]})
                if len(hits) >= max_results:
                    return hits
    return hits


def _related_tests(base: Path, module_rel: Path) -> list[str]:
    """Find test files for a module (test_x.py, x_test.py, tests/test_x.py)."""
    stem = module_rel.stem
    candidates = [
        module_rel.with_name(f"test_{stem}.py"),
        module_rel.with_name(f"{stem}_test.py"),
        Path("tests") / f"test_{module_rel.name}",
        Path("tests") / f"{stem}_test.py",
    ]
    found: list[str] = []
    for candidate in candidates:
        if (base / candidate).exists():
            found.append(candidate.as_posix())
    return found


def context_pack(root: str | Path = ".", module: str = "") -> str:
    """Bundle a module, its tests and basic facts into a context block."""
    base = Path(root).expanduser().resolve()
    module_rel = Path(module)
    target = base / module_rel
    if not target.exists():
        return f"Error: no such file: {module}"
    parts: list[str] = [f"## Context pack: {module_rel.as_posix()}"]
    try:
        size = target.stat().st_size
        parts.append(f"size: {size} B")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        parts.append(f"lines: {len(lines)}")
    except OSError as exc:
        return f"Error: cannot read {module}: {exc}"
    related = _related_tests(base, module_rel)
    if related:
        parts.append("related tests:")
        for test_rel in related:
            test_lines = (
                base / test_rel
            ).read_text(encoding="utf-8", errors="replace").splitlines()
            parts.append(f"  {test_rel} ({len(test_lines)} lines)")
    parts.append("first 40 lines:")
    parts.extend(lines[:40])
    if len(lines) > 40:
        parts.append(f"… ({len(lines) - 40} more lines)")
    return "\n".join(parts)


def _tool_repo_scan(path: str = ".") -> str:
    return format_index(scan(path))


def _tool_repo_search(query: str, path: str = ".", file_types: str | None = None) -> str:
    types = [t.strip() for t in file_types.split(",")] if file_types else None
    hits = search(path, query, file_types=types)
    if not hits:
        return f"(no matches for: {query})"
    return "\n".join(
        f"{hit['path']}:{hit['line']}: {hit['text']}" for hit in hits
    )


def _tool_repo_context(path: str, module: str) -> str:
    return context_pack(path, module)


def make_repo_tools() -> list[Tool]:
    """Agent tools for repo understanding (D1)."""
    return [
        Tool(
            "repo_scan",
            "Index a repository: files, sizes, tree (respects .gitignore). "
            "Returns a markdown tree + per-file size list. Use before "
            "editing unfamiliar code.",
            _tool_repo_scan,
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Repo root (default: current working directory).",
                    },
                },
                "required": [],
            },
            mutates=False,
        ),
        Tool(
            "repo_search",
            "Regex search inside a repository; returns 'path:line: <match>' "
            "lines, or '(no matches)'. Set file_types to limit scope (comma-"
            "separated extensions starting with '.', e.g. '.py,.md').",
            _tool_repo_search,
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "regex pattern to search for.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Repo root (default: cwd).",
                    },
                    "file_types": {
                        "type": "string",
                        "description": "Comma-separated extensions filter (e.g. '.py,.md').",
                    },
                },
                "required": ["query"],
            },
            mutates=False,
        ),
        Tool(
            "repo_context",
            "Bundle a module with its related tests (context pack). "
            "Returns concatenated source + related test-files. Useful for "
            "LLM context when reviewing or editing a module.",
            _tool_repo_context,
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Repo root (default: cwd).",
                    },
                    "module": {
                        "type": "string",
                        "description": (
                            "Relative module path (e.g. 'src/x.py'). "
                            "Tests are discovered automatically (test_*.py "
                            "matching pattern)."
                        ),
                    },
                },
                "required": ["module"],
            },
            mutates=False,
        ),
    ]
