"""Test file_safety (Phase 2, H2/H14/H15/H16/H18)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from eaccode import file_safety
from eaccode.file_safety import (
    build_write_denied_paths,
    build_write_denied_prefixes,
    is_write_denied,
)


@pytest.fixture
def home_dir(tmp_path: Path) -> Path:
    """Create a fake home with sensitive dirs."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    (fake_home / ".ssh").mkdir()
    (fake_home / ".ssh" / "authorized_keys").write_text("key")
    (fake_home / ".aws").mkdir()
    (fake_home / ".netrc").write_text("creds")
    return fake_home


class TestBuildPaths:
    def test_includes_ssh_keys(self, home_dir: Path) -> None:
        paths = build_write_denied_paths(home_dir)
        assert str((home_dir / ".ssh" / "authorized_keys").resolve()) in paths
        assert str((home_dir / ".ssh" / "id_rsa").resolve()) in paths

    def test_includes_dotenv(self, home_dir: Path, tmp_path: Path) -> None:
        paths = build_write_denied_paths(home_dir)
        assert str(home_dir / ".env") in paths or any(
            ".env" in p for p in paths
        )


class TestPrefixes:
    def test_includes_aws_dir(self, home_dir: Path) -> None:
        prefixes = build_write_denied_prefixes(home_dir)
        assert any(
            str((home_dir / ".aws").resolve()) in p for p in prefixes
        )

    def test_includes_ssh_dir(self, home_dir: Path) -> None:
        prefixes = build_write_denied_prefixes(home_dir)
        assert any(
            str((home_dir / ".ssh").resolve()) in p for p in prefixes
        )

    def test_includes_etc_sudoers_d(self) -> None:
        if os.name == "nt":
            pytest.skip("Unix-only path")
        prefixes = build_write_denied_prefixes(Path("/home/x"))
        assert any("sudoers.d" in p or "sudoers" in p for p in prefixes)


class TestIsWriteDenied:
    def test_blocks_ssh_authorized_keys(self, home_dir: Path) -> None:
        target = home_dir / ".ssh" / "authorized_keys"
        # Re-direct the cached denied-paths to the fake home
        import eaccode.file_safety as fs

        fs._DENY_PATHS = build_write_denied_paths(home_dir)
        fs._DENY_PREFIXES = build_write_denied_prefixes(home_dir)
        try:
            assert is_write_denied(str(target.resolve())) is True
        finally:
            fs._DENY_PATHS = None
            fs._DENY_PREFIXES = None

    def test_blocks_aws_dir(self, home_dir: Path) -> None:
        # .aws already exists via fixture (as dir). Just touch a file inside it.
        target = home_dir / ".aws" / "credentials"
        import eaccode.file_safety as fs

        fs._DENY_PATHS = build_write_denied_paths(home_dir)
        fs._DENY_PREFIXES = build_write_denied_prefixes(home_dir)
        try:
            assert is_write_denied(str(target.resolve())) is True
        finally:
            fs._DENY_PATHS = None
            fs._DENY_PREFIXES = None

    def test_allows_normal_file(self, home_dir: Path) -> None:
        normal = home_dir / "Documents" / "notes.txt"
        normal.parent.mkdir()
        normal.write_text("hello")
        import eaccode.file_safety as fs

        fs._DENY_PATHS = build_write_denied_paths(home_dir)
        fs._DENY_PREFIXES = build_write_denied_prefixes(home_dir)
        try:
            assert is_write_denied(str(normal.resolve())) is False
        finally:
            fs._DENY_PATHS = None
            fs._DENY_PREFIXES = None


class TestSafeRoots:
    def test_safe_root_whitelists(self, home_dir: Path) -> None:
        # Pretend a sensitive-looking target is whitelisted
        target = home_dir / ".aws"
        old_env = os.environ.get("EACCODE_WRITE_SAFE_ROOT")
        os.environ["EACCODE_WRITE_SAFE_ROOT"] = str(target.resolve())
        try:
            assert is_write_denied(str(target.resolve())) is False
        finally:
            if old_env is None:
                del os.environ["EACCODE_WRITE_SAFE_ROOT"]
            else:
                os.environ["EACCODE_WRITE_SAFE_ROOT"] = old_env

    def test_safe_root_empty(self) -> None:
        # No env-set: write_safe_roots is empty
        old_env = os.environ.get("EACCODE_WRITE_SAFE_ROOT")
        os.environ.pop("EACCODE_WRITE_SAFE_ROOT", None)
        from eaccode.file_safety import get_safe_write_roots

        assert get_safe_write_roots() == set()
