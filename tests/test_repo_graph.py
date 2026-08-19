"""Tests for repo_graph (Plan I P1.9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode.repo_graph import (
    Definition,
    GraphEdge,
    RepoGraph,
    build_repo_graph,
    cache_dir,
    cached_repo_graph,
    find_definitions,
)


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Build a small Python repo for testing."""
    (tmp_path / "main.py").write_text(
        """\
import os
from helper import compute
from .sibling import do_thing

def main():
    x = compute(1)
    y = do_thing(x)
    print(y)
""",
        encoding="utf-8",
    )
    (tmp_path / "helper.py").write_text(
        """\
def compute(n):
    return n * 2

def helper_func(x):
    return compute(x + 1)
""",
        encoding="utf-8",
    )
    (tmp_path / "sibling.py").write_text(
        """\
def do_thing(x):
    return x + 1

class Widget:
    def render(self):
        return do_thing(self.x)
""",
        encoding="utf-8",
    )
    return tmp_path


class TestModuleName:
    def test_simple(self, tmp_path: Path) -> None:
        from eaccode.repo_graph import _module_name_from_path
        path = tmp_path / "foo.py"
        assert _module_name_from_path(path, tmp_path) == "foo"

    def test_nested(self, tmp_path: Path) -> None:
        from eaccode.repo_graph import _module_name_from_path
        sub = tmp_path / "pkg"
        sub.mkdir()
        path = sub / "bar.py"
        assert _module_name_from_path(path, tmp_path) == "pkg.bar"

    def test_init(self, tmp_path: Path) -> None:
        from eaccode.repo_graph import _module_name_from_path
        sub = tmp_path / "pkg"
        sub.mkdir()
        path = sub / "__init__.py"
        assert _module_name_from_path(path, tmp_path) == "pkg"


class TestBuildRepoGraph:
    def test_finds_imports(self, sample_repo) -> None:
        graph = build_repo_graph(sample_repo)
        # We expect at least these imports from main.py
        import_edges = [e for e in graph.edges if e.kind == "import"]
        assert any(e.src == "main" for e in import_edges)

    def test_finds_calls(self, sample_repo) -> None:
        graph = build_repo_graph(sample_repo)
        # main.main calls compute
        call_edges = [e for e in graph.edges if e.kind == "call"]
        assert any(e.src == "main.main" and e.dst == "compute" for e in call_edges)

    def test_skips_venv(self, sample_repo) -> None:
        venv = sample_repo / ".venv" / "lib"
        venv.mkdir(parents=True)
        (venv / "ignored.py").write_text("def ignored(): pass", encoding="utf-8")
        graph = build_repo_graph(sample_repo)
        sources = {e.src for e in graph.edges}
        assert not any("ignored" in s for s in sources)

    def test_skips_pycache(self, sample_repo) -> None:
        pyc = sample_repo / "__pycache__"
        pyc.mkdir()
        (pyc / "x.py").write_text("def x(): pass", encoding="utf-8")
        graph = build_repo_graph(sample_repo)
        sources = {e.src for e in graph.edges}
        assert not any(s.startswith("__pycache__") for s in sources)


class TestFindDefinitions:
    def test_finds_function(self, sample_repo) -> None:
        defs = find_definitions(sample_repo, "compute")
        assert any(d.kind == "function" and d.module == "helper" for d in defs)

    def test_finds_class(self, sample_repo) -> None:
        defs = find_definitions(sample_repo, "Widget")
        assert any(d.kind == "class" and d.module == "sibling" for d in defs)

    def test_missing_returns_empty(self, sample_repo) -> None:
        assert find_definitions(sample_repo, "no_such_symbol") == []


class TestCache:
    def test_cache_dir_created(self) -> None:
        d = cache_dir()
        assert "eaccode" in str(d)

    def test_cached_repo_graph(self, sample_repo) -> None:
        g1 = cached_repo_graph(sample_repo)
        g2 = cached_repo_graph(sample_repo)
        # Same number of edges (cache hit)
        assert len(g1.edges) == len(g2.edges)