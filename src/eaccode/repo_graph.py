"""Repo graph + search (Plan I P1.9).

Two AST-based tools for understanding a Python codebase:

- ``repo_graph(path, mode="imports"|"calls"|"all")`` builds a directed
  graph of module imports + function call edges. Output is a simple
  adjacency list as text.
- ``repo_search(path, name)`` finds all definitions of ``name`` in
  the repo: classes, functions, top-level assignments.

Caching: results are cached by ``(path, mtime, mode)`` so repeated
calls don't re-parse. Cache lives at
``~/.local/share/eaccode/repo-cache/``.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# AST traversal
# ---------------------------------------------------------------------------

@dataclass
class GraphEdge:
    src: str  # "module:func" or "module"
    dst: str
    kind: str  # "import" | "call"


@dataclass
class RepoGraph:
    """A directed graph of import + call edges in a Python codebase."""
    edges: list[GraphEdge] = field(default_factory=list)

    def imports_of(self, module: str) -> list[str]:
        return sorted({e.dst for e in self.edges if e.kind == "import" and e.src == module})

    def calls_of(self, func: str) -> list[str]:
        return sorted({e.dst for e in self.edges if e.kind == "call" and e.src == func})

    def format(self, mode: str = "all") -> str:
        """Return a text-format graph."""
        out: list[str] = []
        for e in self.edges:
            if mode == "imports" and e.kind != "import":
                continue
            if mode == "calls" and e.kind != "call":
                continue
            out.append(f"{e.src} --[{e.kind}]--> {e.dst}")
        return "\n".join(out) if out else "(empty)"


def _module_name_from_path(path: Path, root: Path) -> str:
    """Map a Python file path to a dotted module name."""
    rel = path.relative_to(root)
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts and parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(p for p in parts if p)


def _parse_file(path: Path, root: Path) -> tuple[str, list[GraphEdge]]:
    """Parse one .py file and return (module_name, edges)."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", []
    try:
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, ValueError):
        return _module_name_from_path(path, root), []

    module = _module_name_from_path(path, root)
    edges: list[GraphEdge] = []

    # Walk the AST looking for imports + function definitions + calls.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(GraphEdge(src=module, dst=alias.name, kind="import"))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                edges.append(GraphEdge(src=module, dst=f"{mod}.{alias.name}", kind="import"))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            full = f"{module}.{node.name}"
            # Find calls inside this function
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    target = _call_target_name(sub)
                    if target:
                        edges.append(GraphEdge(src=full, dst=target, kind="call"))
    return module, edges


def _call_target_name(call: ast.Call) -> str:
    """Best-effort name extraction from a Call node."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        # Recurse to root
        parts: list[str] = []
        cur = func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def build_repo_graph(root: Path) -> RepoGraph:
    """Build a graph by walking all ``.py`` files under ``root``."""
    if not root.exists():
        return RepoGraph()
    graph = RepoGraph()
    for path in root.rglob("*.py"):
        # Skip hidden / vendored / test fixtures quickly
        parts = path.parts
        if any(p.startswith(".") for p in parts):
            continue
        if any(p in {"__pycache__", "node_modules", ".venv", "venv"} for p in parts):
            continue
        _, edges = _parse_file(path, root)
        graph.edges.extend(edges)
    return graph


# ---------------------------------------------------------------------------
# repo_search - find definitions
# ---------------------------------------------------------------------------

@dataclass
class Definition:
    """A single definition found by repo_search."""
    name: str
    kind: str  # "function" | "class" | "assignment"
    module: str
    line: int


def find_definitions(root: Path, name: str, max_results: int = 50) -> list[Definition]:
    """Find all definitions of ``name`` in the repo."""
    if not root.exists():
        return []
    out: list[Definition] = []
    for path in root.rglob("*.py"):
        parts = path.parts
        if any(p.startswith(".") for p in parts):
            continue
        if any(p in {"__pycache__", "node_modules", ".venv", "venv"} for p in parts):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, ValueError):
            continue

        module = _module_name_from_path(path, root)
        for node in ast.walk(tree):
            if len(out) >= max_results:
                return out
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                out.append(Definition(name=name, kind="function", module=module, line=node.lineno))
            elif isinstance(node, ast.ClassDef) and node.name == name:
                out.append(Definition(name=name, kind="class", module=module, line=node.lineno))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == name:
                        out.append(Definition(name=name, kind="assignment", module=module, line=node.lineno))
    return out


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "eaccode" / "repo-cache"
    return Path.home() / ".local" / "share" / "eaccode" / "repo-cache"


def _cache_key(root: Path, mode: str) -> str:
    """Cache key based on root path + max mtime of any .py file."""
    try:
        latest = max(
            (p.stat().st_mtime for p in root.rglob("*.py") if not any(part.startswith(".") for part in p.parts)),
            default=0,
        )
    except OSError:
        latest = 0
    raw = f"{root.resolve()}|{mode}|{latest}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def cached_repo_graph(root: Path, mode: str = "all") -> RepoGraph:
    """Build the graph with disk cache."""
    cache = cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    key = _cache_key(root, mode)
    cache_file = cache / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            graph = RepoGraph(
                edges=[GraphEdge(**e) for e in data.get("edges", [])],
            )
            return graph
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    graph = build_repo_graph(root)
    try:
        cache_file.write_text(
            json.dumps({"edges": [e.__dict__ for e in graph.edges]}),
            encoding="utf-8",
        )
    except OSError:
        pass
    return graph


__all__ = [
    "GraphEdge",
    "RepoGraph",
    "Definition",
    "build_repo_graph",
    "find_definitions",
    "cached_repo_graph",
    "cache_dir",
]