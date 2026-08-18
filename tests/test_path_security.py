"""Tests for path_security (Plan H.minimal v4, Tag 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import path_security as ps
from eaccode.workspace import WorkspaceError


class TestHasTraversal:
    def test_simple_dotdot(self) -> None:
        assert ps.has_traversal_component("../foo") is True

    def test_multiple(self) -> None:
        assert ps.has_traversal_component("foo/../../bar") is True

    def test_absolute_with_traversal(self) -> None:
        assert ps.has_traversal_component("/etc/../etc/passwd") is True

    def test_clean_path(self) -> None:
        assert ps.has_traversal_component("foo/bar") is False

    def test_dotdot_in_filename(self) -> None:
        """``..`` in the filename (e.g. ``foo..txt``) is NOT traversal."""
        assert ps.has_traversal_component("foo..txt") is False


class TestBlockedDevice:
    def test_windows_aux(self) -> None:
        assert ps.is_blocked_device("C:/aux") is True

    def test_windows_con(self) -> None:
        assert ps.is_blocked_device("./CON") is True

    def test_windows_com1(self) -> None:
        assert ps.is_blocked_device("COM1") is True

    def test_nul(self) -> None:
        assert ps.is_blocked_device("NUL") is True

    def test_normal_file(self) -> None:
        assert ps.is_blocked_device("foo.txt") is False

    def test_con_prefix(self) -> None:
        """``CON.txt`` is a normal file, not the CON device."""
        assert ps.is_blocked_device("CON.txt") is False

    def test_dev_null(self) -> None:
        assert ps.is_blocked_device("/dev/null") is True

    def test_dev_normal(self) -> None:
        assert ps.is_blocked_device("/dev/myapp.sock") is False


class TestUncPath:
    def test_windows_unc(self) -> None:
        assert ps.is_unc_path("\\\\server\\share") is True

    def test_posix_unc(self) -> None:
        assert ps.is_unc_path("//server/share") is True

    def test_normal_path(self) -> None:
        assert ps.is_unc_path("C:/Users/foo") is False

    def test_double_backslash_only(self) -> None:
        # ``\\foo`` (only one segment after backslashes) is not UNC
        assert ps.is_unc_path("\\\\") is False


class TestPathWithinDir:
    def test_within(self, tmp_path) -> None:
        inside = tmp_path / "foo.txt"
        inside.touch()
        assert ps.is_path_within_dir(inside, tmp_path) is True

    def test_outside(self, tmp_path) -> None:
        outside = tmp_path / "sub" / "outside.txt"
        outside.parent.mkdir()
        outside.touch()
        root = tmp_path / "root"
        root.mkdir()
        assert ps.is_path_within_dir(outside, root) is False

    def test_relative_to_absolute(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        inside = tmp_path / "foo.txt"
        inside.touch()
        assert ps.is_path_within_dir("./foo.txt", tmp_path) is True


class TestValidateWithinDir:
    def test_valid(self, tmp_path) -> None:
        f = tmp_path / "foo.txt"
        f.touch()
        result = ps.validate_within_dir(str(f), str(tmp_path))
        assert result == f.resolve()

    def test_traversal_raises(self, tmp_path) -> None:
        with pytest.raises(WorkspaceError) as exc:
            ps.validate_within_dir("../foo.txt", str(tmp_path))
        assert exc.value.code == "path_traversal"

    def test_blocked_device_raises(self, tmp_path) -> None:
        with pytest.raises(WorkspaceError) as exc:
            ps.validate_within_dir("C:/aux", str(tmp_path))
        assert exc.value.code == "blocked_device"

    def test_unc_raises(self, tmp_path) -> None:
        with pytest.raises(WorkspaceError) as exc:
            ps.validate_within_dir("\\\\server\\share", str(tmp_path))
        assert exc.value.code == "unc_path"

    def test_outside_raises(self, tmp_path) -> None:
        other = tmp_path / "other"
        other.mkdir()
        f = other / "x.txt"
        f.touch()
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises(WorkspaceError) as exc:
            ps.validate_within_dir(str(f), str(root))
        assert exc.value.code == "path_outside_root"