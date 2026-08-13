"""Git & PR tools (Phase D4): read-only inspection, commits, branches, PRs.

Safety rules (documented in tool descriptions):
- never commit while tests are red (run run_tests first)
- git_commit_undo only resets the last soft commit (no pushed history)
- gh CLI is optional; a clean error explains how to install it
"""

from __future__ import annotations

import shutil
import subprocess

from eaccode.agent import Tool

GIT_TIMEOUT = 60


def _git(cwd: str, *args: str) -> tuple[int, str]:
    """Run a git command; returns (exit_code, output)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return 124, f"Error: git timed out: {' '.join(args)}"
    except OSError as exc:
        return 127, f"Error: git unavailable: {exc}"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output.strip()


def _is_repo(cwd: str) -> bool:
    return _git(cwd, "rev-parse", "--is-inside-work-tree")[0] == 0


def git_status(cwd: str = ".") -> str:
    if not _is_repo(cwd):
        return "Error: not a git repository (or cwd is not inside one)"
    code, out = _git(cwd, "status", "--short", "--branch")
    return out if code == 0 else f"Error: {out}"


def git_diff(cwd: str = ".", stat: bool = False) -> str:
    if not _is_repo(cwd):
        return "Error: not a git repository"
    args = ["diff"]
    if stat:
        args.append("--stat")
    code, out = _git(cwd, *args)
    return out if code == 0 else f"Error: {out}"


def git_log(cwd: str = ".", limit: int = 10) -> str:
    if not _is_repo(cwd):
        return "Error: not a git repository"
    code, out = _git(
        cwd, "log", f"-{limit}", "--pretty=format:%h %s"
    )
    return out if code == 0 else f"Error: {out}"


def git_branch(cwd: str = ".") -> str:
    if not _is_repo(cwd):
        return "Error: not a git repository"
    code, out = _git(cwd, "branch", "--list")
    return out if code == 0 else f"Error: {out}"


def git_commit(cwd: str = ".", message: str = "") -> str:
    """Stage all changes and commit. Policy: run tests before committing."""
    if not message.strip():
        return "Error: commit message is required"
    if not _is_repo(cwd):
        return "Error: not a git repository"
    code, out = _git(cwd, "add", "-A")
    if code != 0:
        return f"Error: git add failed: {out}"
    code, out = _git(cwd, "commit", "-m", message)
    if code != 0:
        return f"Error: commit failed: {out}"
    return f"committed: {out.splitlines()[0] if out else message}"


def git_commit_undo(cwd: str = ".") -> str:
    """Soft-reset the last commit (working tree stays intact)."""
    if not _is_repo(cwd):
        return "Error: not a git repository"
    code, out = _git(cwd, "rev-parse", "--verify", "HEAD~1")
    if code != 0:
        return "Error: nothing to undo (only one commit / no history)"
    code, out = _git(cwd, "reset", "--soft", "HEAD~1")
    return "undone: last commit reset (changes stay staged)" if code == 0 else f"Error: {out}"


def git_branch_new(cwd: str = ".", name: str = "") -> str:
    if not name.strip():
        return "Error: branch name is required"
    if not _is_repo(cwd):
        return "Error: not a git repository"
    code, out = _git(cwd, "checkout", "-b", name)
    return f"branch created: {name}" if code == 0 else f"Error: {out}"


def git_push(cwd: str = ".", remote: str = "origin") -> str:
    if not _is_repo(cwd):
        return "Error: not a git repository"
    code, out = _git(cwd, "push", "-u", remote, "HEAD")
    return out if code == 0 else f"Error: {out}"


def git_pr(cwd: str = ".", title: str = "", body: str = "") -> str:
    """Open a PR via gh CLI when available; else explain the next steps."""
    if not shutil.which("gh"):
        return (
            "Error: gh CLI not installed. Install GitHub CLI, then: "
            "gh auth login && gh pr create --title ... --body ..."
        )
    if not title.strip():
        return "Error: PR title is required"
    command = ["gh", "pr", "create", "--title", title]
    if body:
        command += ["--body", body]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return f"Error: gh failed: {exc}"
    output = ((result.stdout or "") + (result.stderr or "")).strip()
    if result.returncode != 0:
        return f"Error: {output}"
    return output or f"PR created: {title}"


def _tool_git_status(path: str = ".") -> str:
    return git_status(path)


def _tool_git_diff(path: str = ".", stat: bool = False) -> str:
    return git_diff(path, stat)


def _tool_git_log(path: str = ".", limit: int = 10) -> str:
    return git_log(path, limit)


def _tool_git_commit(path: str = ".", message: str = "") -> str:
    return git_commit(path, message)


def _tool_git_branch_new(path: str = ".", name: str = "") -> str:
    return git_branch_new(path, name)


def make_git_tools() -> list[Tool]:
    """Agent tools for git/PR workflows (D4)."""
    return [
        Tool(
            "git_status",
            "Show the working tree status of a git repository.",
            _tool_git_status,
            {"type": "object", "properties": {"path": {"type": "string"}}},
        ),
        Tool(
            "git_diff",
            "Show uncommitted changes (optionally as a stat summary).",
            _tool_git_diff,
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "stat": {"type": "boolean"},
                },
            },
        ),
        Tool(
            "git_log",
            "Show the last commits (hash + subject).",
            _tool_git_log,
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "limit": {"type": "integer"},
                },
            },
        ),
        Tool(
            "git_commit",
            "Stage all changes and commit with a message. Policy: run "
            "run_tests first — never commit while tests are red.",
            _tool_git_commit,
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["message"],
            },
        ),
        Tool(
            "git_branch_new",
            "Create and switch to a new branch.",
            _tool_git_branch_new,
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            "git_commit_undo",
            "Soft-reset the last commit (changes stay in the working tree).",
            lambda path=".": git_commit_undo(path),
            {"type": "object", "properties": {"path": {"type": "string"}}},
        ),
    ]
