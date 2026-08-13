"""Tests for repo understanding (Phase D1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import config as cfg
from eaccode import repo


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """A small repo with .gitignore, sources and tests."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        "MAX_TURNS = 10\n\ndef run():\n    print('hallo')\n", encoding="utf-8"
    )
    (tmp_path / "src" / "app_test.py").write_text("def test_run(): pass\n", encoding="utf-8")
    (tmp_path / "tests" / "test_app.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("# Notes\nMAX_TURNS is important\n", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("MAX_TURNS=secret\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("*.txt\n!keep.txt\n", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("keep me\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("x\n", encoding="utf-8")
    return tmp_path


class TestIgnoreRules:
    def test_basename_pattern(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.txt\n", encoding="utf-8")
        rules = repo.IgnoreRules.from_file(tmp_path / ".gitignore")
        assert rules.is_ignored("secret.txt")
        assert rules.is_ignored("deep/dir/secret.txt")

    def test_negation_wins(self, sample_repo: Path) -> None:
        rules = repo.IgnoreRules.from_file(sample_repo / ".gitignore")
        assert rules.is_ignored("x.txt")
        assert not rules.is_ignored("keep.txt")

    def test_dir_only_pattern(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("build/\n", encoding="utf-8")
        rules = repo.IgnoreRules.from_file(tmp_path / ".gitignore")
        assert rules.is_ignored("build/out.js")
        assert not rules.is_ignored("buildx/out.js")

    def test_double_star(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("**/logs/*.log\n", encoding="utf-8")
        rules = repo.IgnoreRules.from_file(tmp_path / ".gitignore")
        assert rules.is_ignored("a/b/logs/x.log")


class TestScan:
    def test_scan_finds_files_with_sizes(self, sample_repo: Path) -> None:
        index = repo.scan(sample_repo)
        paths = {entry.path for entry in index.entries}
        assert "src/app.py" in paths
        assert "tests/test_app.py" in paths
        assert "keep.txt" in paths  # negation keeps it
        assert all(entry.size > 0 for entry in index.entries)

    def test_scan_respects_gitignore_and_always_ignored(self, sample_repo: Path) -> None:
        index = repo.scan(sample_repo)
        paths = {entry.path for entry in index.entries}
        assert "secret.txt" not in paths
        assert "node_modules/lib.js" not in paths

    def test_scan_missing_dir(self, tmp_path: Path) -> None:
        index = repo.scan(tmp_path / "ghost")
        assert index.entries == []

    def test_scan_max_files(self, sample_repo: Path) -> None:
        index = repo.scan(sample_repo, max_files=2)
        assert len(index.entries) <= 2
        assert index.truncated

    def test_format_index(self, sample_repo: Path) -> None:
        text = repo.format_index(repo.scan(sample_repo))
        assert "files:" in text
        assert "src/app.py" in text


class TestSearch:
    def test_finds_matches(self, sample_repo: Path) -> None:
        hits = repo.search(sample_repo, "MAX_TURNS")
        assert any(hit["path"] == "src/app.py" and hit["line"] == 1 for hit in hits)

    def test_file_type_filter(self, sample_repo: Path) -> None:
        hits = repo.search(sample_repo, "MAX_TURNS", file_types=[".py"])
        assert {hit["path"] for hit in hits} == {"src/app.py"}

    def test_ignores_gitignored_files(self, sample_repo: Path) -> None:
        hits = repo.search(sample_repo, "MAX_TURNS")
        assert not any(hit["path"] == "secret.txt" for hit in hits)

    def test_invalid_regex(self, sample_repo: Path) -> None:
        hits = repo.search(sample_repo, "([")
        assert "invalid regex" in hits[0]["text"]

    def test_max_results(self, sample_repo: Path) -> None:
        hits = repo.search(sample_repo, "a", max_results=3)
        assert len(hits) <= 3


class TestContextPack:
    def test_bundles_module_and_tests(self, sample_repo: Path) -> None:
        pack = repo.context_pack(sample_repo, "src/app.py")
        assert "## Context pack: src/app.py" in pack
        assert "MAX_TURNS" in pack
        assert "related tests:" in pack
        assert "src/app_test.py" in pack
        assert "tests/test_app.py" in pack

    def test_missing_module(self, sample_repo: Path) -> None:
        pack = repo.context_pack(sample_repo, "ghost.py")
        assert "Error" in pack


class TestTools:
    def test_make_repo_tools(self, sample_repo: Path) -> None:
        tools = {tool.name: tool for tool in repo.make_repo_tools()}
        assert set(tools) == {"repo_scan", "repo_search", "repo_context"}
        out = tools["repo_scan"].func(str(sample_repo))
        assert "src/app.py" in out
        out = tools["repo_search"].func("MAX_TURNS", str(sample_repo), ".py")
        assert "src/app.py:1" in out
        out = tools["repo_context"].func(str(sample_repo), "src/app.py")
        assert "related tests:" in out


class TestCliIntegration:
    def test_build_agent_includes_repo_tools(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        cfg.ensure_config()
        from eaccode.cli import build_agent

        agent = build_agent()
        names = {tool.name for tool in agent.tools.values()}
        assert {"repo_scan", "repo_search", "repo_context"} <= names
