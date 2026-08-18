"""Tests for workspace (Plan H.minimal v3, Stufe 1)."""

from __future__ import annotations

import pytest

from eaccode import workspace as ws
from eaccode.workspace import (
    EXEMPT_PATH_FRAGMENTS,
    Workspace,
    WorkspaceError,
    get_default_workspace,
    load_workspace_from_config,
    rewrite_path,
)


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    """Create a fresh workspace rooted at a tmp dir."""
    root = tmp_path / ".eaccode-workspace"
    root.mkdir()
    return Workspace(root=root.resolve())


class TestRewrite:
    def test_empty_returns_root(self, workspace) -> None:
        assert rewrite_path("", workspace) == workspace.root

    def test_dot_returns_root(self, workspace) -> None:
        assert rewrite_path(".", workspace) == workspace.root

    def test_relative_simple(self, workspace) -> None:
        result = rewrite_path("foo.py", workspace)
        assert result == (workspace.root / "foo.py").resolve(strict=False)

    def test_relative_nested(self, workspace) -> None:
        result = rewrite_path("subdir/foo.py", workspace)
        assert result == (workspace.root / "subdir" / "foo.py").resolve(strict=False)

    def test_relative_parent_traversal_blocked(self, workspace) -> None:
        """``../secrets`` would escape the workspace."""
        with pytest.raises(WorkspaceError) as exc:
            rewrite_path("../secrets", workspace)
        assert exc.value.code == "path_traversal"

    def test_absolute_outside_blocked(self, workspace) -> None:
        with pytest.raises(WorkspaceError) as exc:
            rewrite_path("/etc/passwd", workspace)
        assert exc.value.code == "absolute_outside_workspace"

    def test_absolute_windows_outside_blocked(self, workspace) -> None:
        with pytest.raises(WorkspaceError) as exc:
            rewrite_path("C:/Users/admin/secret.txt", workspace)
        assert exc.value.code == "absolute_outside_workspace"

    def test_tilde_redirects_to_workspace(self, workspace) -> None:
        result = rewrite_path("~/foo.py", workspace)
        assert result.is_relative_to(workspace.root) or result.parent == workspace.root

    def test_exempt_memory(self, workspace) -> None:
        """MEMORY.md bypasses the workspace."""
        path = rewrite_path("C:/Users/x/AppData/Local/eaccode/MEMORY.md", workspace)
        # No WorkspaceError raised - it returned as-is
        assert "MEMORY.md" in str(path)

    def test_exempt_skills(self, workspace) -> None:
        path = rewrite_path("C:/Users/x/AppData/Local/eaccode/skills/foo.md", workspace)
        assert "skills" in str(path)

    def test_allowed_path_overrides_workspace(self, tmp_path) -> None:
        ws_root = tmp_path / ".eaccode-workspace"
        ws_root.mkdir()
        allowed_dir = tmp_path / "shared"
        allowed_dir.mkdir()
        ws_obj = Workspace(
            root=ws_root.resolve(),
            allow_paths=[allowed_dir.resolve()],
        )
        # Allowed path works
        result = rewrite_path(str(allowed_dir / "data.txt"), ws_obj)
        assert str(result).endswith("data.txt")

    def test_denied_path_always_blocked(self, tmp_path) -> None:
        ws_root = tmp_path / ".eaccode-workspace"
        ws_root.mkdir()
        denied_dir = tmp_path / "secret"
        denied_dir.mkdir()
        ws_obj = Workspace(
            root=ws_root.resolve(),
            allow_paths=[denied_dir.resolve()],
            deny_paths=[denied_dir.resolve()],
        )
        with pytest.raises(WorkspaceError) as exc:
            rewrite_path(str(denied_dir / "secret.txt"), ws_obj)
        assert exc.value.code == "explicitly_denied"


class TestWorkspace:
    def test_is_within_true(self, workspace) -> None:
        inside = workspace.root / "foo.py"
        assert workspace.is_within(inside) is True

    def test_is_within_false(self, workspace, tmp_path) -> None:
        outside = tmp_path / "outside.txt"
        outside.touch()
        assert workspace.is_within(outside) is False

    def test_is_denied(self, tmp_path) -> None:
        ws_root = tmp_path / ".eaccode-workspace"
        ws_root.mkdir()
        denied = tmp_path / "secret"
        denied.mkdir()
        ws_obj = Workspace(root=ws_root.resolve(), deny_paths=[denied.resolve()])
        assert ws_obj.is_denied(denied / "x.txt") is True

    def test_is_allowed_outside(self, tmp_path) -> None:
        ws_root = tmp_path / ".eaccode-workspace"
        ws_root.mkdir()
        allowed = tmp_path / "shared"
        allowed.mkdir()
        ws_obj = Workspace(root=ws_root.resolve(), allow_paths=[allowed.resolve()])
        assert ws_obj.is_allowed_outside(allowed / "x.txt") is True


class TestExempt:
    def test_exempt_includes_memory_md(self) -> None:
        assert "MEMORY.md" in EXEMPT_PATH_FRAGMENTS

    def test_exempt_includes_user_md(self) -> None:
        assert "USER.md" in EXEMPT_PATH_FRAGMENTS

    def test_exempt_includes_skills(self) -> None:
        assert "/skills/" in EXEMPT_PATH_FRAGMENTS or "\\skills\\" in EXEMPT_PATH_FRAGMENTS


class TestGetDefaultWorkspace:
    def test_workspace_is_cwd(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        ws_obj = get_default_workspace()
        assert ws_obj.root == tmp_path.resolve()


class TestLoadFromConfig:
    def test_default_workspace_is_cwd(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        ws_obj = load_workspace_from_config({})
        assert ws_obj.root == tmp_path.resolve()

    def test_custom_root_from_config(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        custom_root = tmp_path / "my-workspace"
        ws_obj = load_workspace_from_config({"workspace": {"root": str(custom_root)}})
        assert ws_obj.root == custom_root.resolve()

    def test_allow_paths_from_config(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        allow = tmp_path / "external"
        allow.mkdir()
        ws_obj = load_workspace_from_config(
            {"workspace": {"allow_paths": [str(allow)]}}
        )
        assert ws_obj.allow_paths == [allow.resolve()]
