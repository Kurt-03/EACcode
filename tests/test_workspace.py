"""Tests for workspace (Plan H.minimal v3, Stufe 1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import workspace as ws
from eaccode import workspace as workspace_module
from eaccode.workspace import (
    EXEMPT_PATH_FRAGMENTS,
    Workspace,
    WorkspaceError,
    filter_search_results,
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


class TestPathRule:
    def test_valid_scope(self) -> None:
        rule = ws.PathRule(raw="x", scope="session", kind="allow")
        assert rule.scope == "session"

    def test_invalid_scope_raises(self) -> None:
        with pytest.raises(ValueError):
            ws.PathRule(raw="x", scope="permanent", kind="allow")

    def test_invalid_kind_raises(self) -> None:
        with pytest.raises(ValueError):
            ws.PathRule(raw="x", scope="session", kind="reject")


class TestRuntimeMutation:
    def test_add_allow_returns_rule(self, workspace) -> None:
        rule = workspace.add_allow("C:/Users/admin/Desktop", scope="session")
        assert rule.kind == "allow"
        assert rule.scope == "session"
        assert rule.raw == "C:/Users/admin/Desktop"

    def test_add_deny_returns_rule(self, workspace) -> None:
        rule = workspace.add_deny("C:/Users/admin/secrets", scope="always")
        assert rule.kind == "deny"
        assert rule.scope == "always"

    def test_list_rules_returns_all(self, workspace) -> None:
        workspace.add_allow("a", scope="session")
        workspace.add_allow("b", scope="session")
        workspace.add_deny("c", scope="always")
        assert len(workspace.list_rules()) == 3

    def test_remove_rule(self, workspace) -> None:
        rule = workspace.add_allow("a", scope="session")
        workspace.remove_rule(rule)
        assert rule not in workspace.list_rules()

    def test_add_allow_resolves_into_paths(self, tmp_path) -> None:
        ws_root = tmp_path / ".eaccode-workspace"
        ws_root.mkdir()
        allowed = tmp_path / "shared"
        allowed.mkdir()
        ws_obj = Workspace(root=ws_root.resolve())
        ws_obj.add_allow(str(allowed), scope="session")
        assert allowed.resolve() in ws_obj.allow_paths


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


class TestSessionCwd:
    def test_update_session_cwd(self, tmp_path, monkeypatch) -> None:
        workspace_module._session_cwd = None
        workspace_module._active_workspace = None
        monkeypatch.chdir(tmp_path)
        workspace_module.update_session_cwd(tmp_path / "subdir")
        ws_obj = workspace_module.get_active_workspace()
        assert ws_obj.root == (tmp_path / "subdir").resolve()
        workspace_module._session_cwd = None
        workspace_module._active_workspace = None

    def test_get_session_cwd(self, tmp_path, monkeypatch) -> None:
        workspace_module._session_cwd = None
        workspace_module._active_workspace = None
        monkeypatch.chdir(tmp_path)
        assert workspace_module.get_session_cwd() is None
        workspace_module.update_session_cwd(tmp_path / "other")
        assert workspace_module.get_session_cwd() == (tmp_path / "other").resolve()
        workspace_module._session_cwd = None
        workspace_module._active_workspace = None


class TestExpandTilde:
    def test_no_tilde(self) -> None:
        from eaccode.workspace import expand_tilde
        assert expand_tilde("foo/bar") == "foo/bar"

    def test_tilde_alone(self) -> None:
        from eaccode.workspace import expand_tilde
        result = expand_tilde("~")
        assert result == str(Path.home())

    def test_tilde_slash(self) -> None:
        from eaccode.workspace import expand_tilde
        result = expand_tilde("~/foo.txt")
        assert result == str(Path.home() / "foo.txt")


class TestFilterSearchResults:
    def test_filters_blocked_paths(self) -> None:
        from eaccode.workspace import filter_search_results
        ws_obj = Workspace(root=Path.cwd().resolve())
        results = [
            "src/main.py:1:hello",
            "/home/user/.ssh/id_rsa:1:sensitive",
            "/home/user/.aws/credentials:1:secret",
        ]
        filtered = filter_search_results(results, ws_obj)
        assert "src/main.py:1:hello" in filtered
        assert ".ssh/id_rsa" not in str(filtered)
        assert ".aws/credentials" not in str(filtered)
        assert "filtered" in str(filtered).lower()

    def test_keeps_normal_paths(self) -> None:
        from eaccode.workspace import filter_search_results
        ws_obj = Workspace(root=Path.cwd().resolve())
        results = ["src/foo.py:1:bar", "tests/baz.py:2:qux"]
        filtered = filter_search_results(results, ws_obj)
        assert len(filtered) == 2

    def test_allowed_paths_pass_through(self, tmp_path) -> None:
        from eaccode.workspace import filter_search_results
        ssh_dir = tmp_path / "ssh"
        ssh_dir.mkdir()
        ws_obj = Workspace(
            root=tmp_path.resolve(),
            allow_paths=[ssh_dir],
        )
        results = [f"{ssh_dir}/id_rsa:1:hi"]
        filtered = filter_search_results(results, ws_obj)
        # When allow-listed, the path passes through
        assert f"{ssh_dir}/id_rsa:1:hi" in filtered
