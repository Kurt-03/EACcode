"""Tests for git & PR tools (Phase D4)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from eaccode import git


def _run(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _run(tmp_path, "init", "-q", "-b", "main")
    _run(tmp_path, "config", "user.email", "test@example.com")
    _run(tmp_path, "config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("v1\n", encoding="utf-8")
    _run(tmp_path, "add", "-A")
    _run(tmp_path, "commit", "-q", "-m", "initial")
    return tmp_path


class TestReadOnly:
    def test_status(self, repo: Path) -> None:
        assert "main" in git.git_status(str(repo))

    def test_status_not_a_repo(self, tmp_path: Path) -> None:
        out = git.git_status(str(tmp_path))
        assert "not a git repository" in out

    def test_log(self, repo: Path) -> None:
        out = git.git_log(str(repo))
        assert "initial" in out

    def test_branch(self, repo: Path) -> None:
        assert "* main" in git.git_branch(str(repo))

    def test_diff_empty(self, repo: Path) -> None:
        assert git.git_diff(str(repo)) == ""


class TestCommit:
    def test_commit_works(self, repo: Path) -> None:
        (repo / "a.txt").write_text("v2\n", encoding="utf-8")
        out = git.git_commit(str(repo), "second")
        assert "committed" in out
        log = git.git_log(str(repo))
        assert "second" in log

    def test_commit_requires_message(self, repo: Path) -> None:
        out = git.git_commit(str(repo), "")
        assert "message is required" in out

    def test_undo_resets_soft(self, repo: Path) -> None:
        (repo / "a.txt").write_text("v2\n", encoding="utf-8")
        git.git_commit(str(repo), "second")
        out = git.git_commit_undo(str(repo))
        assert "undone" in out
        assert "second" not in git.git_log(str(repo))
        assert "v2" in (repo / "a.txt").read_text(encoding="utf-8")  # worktree intact

    def test_undo_no_history(self, repo: Path) -> None:
        out = git.git_commit_undo(str(repo))
        assert "nothing to undo" in out


class TestBranches:
    def test_branch_new(self, repo: Path) -> None:
        out = git.git_branch_new(str(repo), "feature/x")
        assert "branch created" in out
        assert "* feature/x" in git.git_branch(str(repo))

    def test_branch_new_requires_name(self, repo: Path) -> None:
        assert "name is required" in git.git_branch_new(str(repo), "")


class TestTools:
    def test_make_git_tools(self) -> None:
        tools = {tool.name: tool for tool in git.make_git_tools()}
        assert {
            "git_status",
            "git_diff",
            "git_log",
            "git_commit",
            "git_branch_new",
            "git_commit_undo",
        } <= set(tools)

    def test_tool_status(self, repo: Path) -> None:
        tools = {tool.name: tool for tool in git.make_git_tools()}
        assert "main" in tools["git_status"].func(str(repo))
