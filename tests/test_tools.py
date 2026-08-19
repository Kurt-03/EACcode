"""Tests for the built-in tools (Phase A5 + Plan H.minimal v3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import tools
from eaccode.workspace import Workspace


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    (tmp_path / "alpha.txt").write_text("hello world\n", encoding="utf-8")
    (tmp_path / "beta.md").write_text("# beta\npattern here\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "gamma.py").write_text("pattern = True\n", encoding="utf-8")
    return tmp_path


@pytest.fixture(autouse=True)
def wire_workspace(sample_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the tool module workspace to sample_dir for every test."""
    ws = Workspace(root=sample_dir.resolve())
    tools._set_workspace(ws)
    yield
    tools._set_workspace(None)  # reset so other tests don't leak


class TestFiles:
    def test_read_file(self, sample_dir: Path) -> None:
        # Use a relative path so the workspace check passes.
        out = tools.read_file("alpha.txt")
        assert out == "hello world\n"

    def test_read_missing_file_returns_error(self) -> None:
        # Absolute path outside the workspace triggers a workspace error
        # rather than an OSError - the workspace check happens first.
        out = tools.read_file("C:/definitely/missing/file.txt")
        assert out.startswith("Error:")
        assert "outside workspace" in out.lower() or "cannot read" in out.lower()

    def test_read_outside_workspace_blocked(self) -> None:
        out = tools.read_file("/etc/passwd")
        assert "Error:" in out
        assert "outside workspace" in out.lower()

    def test_read_truncates(self, sample_dir: Path) -> None:
        (sample_dir / "big.txt").write_text("x" * 10_000, encoding="utf-8")
        out = tools.read_file("big.txt", max_chars=100)
        # New behaviour: explicit WARNING marker so file_edit refuses
        # to use this as old_string.
        assert "WARNING: CONTENT TRUNCATED" in out
        assert "x" in out  # but actual content is there

    def test_read_small_file_unchanged(self, sample_dir: Path) -> None:
        """No truncation marker when file fits in max_chars."""
        (sample_dir / "small.txt").write_text("hello", encoding="utf-8")
        out = tools.read_file("small.txt")
        assert "WARNING" not in out
        assert "hello" in out

    def test_write_file_creates_parents(self, sample_dir: Path) -> None:
        out = tools.write_file("nested/deep/f.txt", "content")
        assert "written" in out or "wrote" in out
        # Workspace is sample_dir
        target = sample_dir / "nested" / "deep" / "f.txt"
        assert target.read_text(encoding="utf-8") == "content"

    def test_write_file_outside_workspace_blocked(self) -> None:
        out = tools.write_file("/etc/passwd", "x")
        assert "Error:" in out
        assert "outside workspace" in out.lower()

    def test_write_file_path_traversal_blocked(self) -> None:
        out = tools.write_file("../escape.txt", "x")
        assert "Error:" in out

    def test_list_files(self, sample_dir: Path) -> None:
        out = tools.list_files(".")
        assert "alpha.txt" in out
        assert "sub/" in out

    def test_search_files_finds_pattern(self, sample_dir: Path) -> None:
        out = tools.search_files("pattern", ".")
        assert "beta.md" in out
        assert "gamma.py" in out

    def test_search_no_match(self, sample_dir: Path) -> None:
        assert tools.search_files("zzz-not-there", ".") == "no matches"

    def test_list_files_outside_workspace_blocked(self) -> None:
        out = tools.list_files("/etc")
        assert "Error:" in out
        assert "outside workspace" in out.lower()


class TestWeb:
    def test_http_get(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self, size: int) -> bytes:
                return b"<html>page content</html>"

        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: FakeResponse())
        assert tools.http_get("https://example.com") == "<html>page content</html>"

    def test_http_get_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        def boom(url: str, timeout: int) -> None:
            raise ConnectionError("refused")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        out = tools.http_get("https://example.com")
        assert out.startswith("Error:")

    def test_web_search_parses_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        html = (
            '<a rel="nofollow" class="result__a" href="https://a.example/x">'
            "First <b>Result</b></a>"
            '<a rel="nofollow" class="result__a" href="https://b.example/y">Second</a>'
        )

        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self, size: int) -> bytes:
                return html.encode("utf-8")

        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: FakeResponse())
        out = tools.web_search("test query")
        assert "First Result" in out
        assert "https://a.example/x" in out
        assert "Second" in out

    def test_web_search_no_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self, size: int) -> bytes:
                return b"<html>nothing</html>"

        import urllib.request

        monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: FakeResponse())
        assert tools.web_search("x") == "(no results)"

    def test_web_search_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.request

        def boom(url: str, timeout: int) -> None:
            raise OSError("network down")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        assert tools.web_search("x").startswith("Error:")


class TestInfo:
    def test_current_time_format(self) -> None:
        out = tools.current_time()
        assert len(out) == 19  # YYYY-MM-DD HH:MM:SS

    def test_system_info(self) -> None:
        out = tools.system_info()
        assert out  # non-empty
        assert " " in out


class TestCatalog:
    def test_builtin_tools_are_registered(self) -> None:
        names = {tool.name for tool in tools.BUILTIN_TOOLS}
        assert {
            "read_file",
            "write_file",
            "list_files",
            "search_files",
            "http_get",
            "web_search",
            "current_time",
            "system_info",
        } <= names

    def test_every_tool_has_description_and_schema(self) -> None:
        for tool in tools.BUILTIN_TOOLS:
            assert tool.description
            assert tool.parameters is not None



class TestStatusLine:
    """Phase B.1: status_line surfaces exit-code warnings."""

    def test_exit_code_marker(self) -> None:
        from eaccode.banner import status_line

        line = status_line("model", 1.5, 100, exit_code=1)
        assert "⚠ exit=1" in line
        assert "model" in line

    def test_success_no_marker(self) -> None:
        from eaccode.banner import status_line

        line = status_line("model", 1.5, 100, exit_code=0)
        assert "⚠" not in line

    def test_warning_marker(self) -> None:
        from eaccode.banner import status_line

        line = status_line("model", 1.5, 100, warning="permission denied")
        assert "⚠" in line
        assert "permission denied" in line
