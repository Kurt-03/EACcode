"""Tests for the built-in tools (Phase A5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import tools


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    (tmp_path / "alpha.txt").write_text("hello world\n", encoding="utf-8")
    (tmp_path / "beta.md").write_text("# beta\npattern here\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "gamma.py").write_text("pattern = True\n", encoding="utf-8")
    return tmp_path


class TestFiles:
    def test_read_file(self, sample_dir: Path) -> None:
        out = tools.read_file(str(sample_dir / "alpha.txt"))
        assert out == "hello world\n"

    def test_read_missing_file_returns_error(self) -> None:
        out = tools.read_file("C:/definitely/missing/file.txt")
        assert out.startswith("Error:")

    def test_read_truncates(self, sample_dir: Path) -> None:
        (sample_dir / "big.txt").write_text("x" * 10_000, encoding="utf-8")
        out = tools.read_file(str(sample_dir / "big.txt"), max_chars=100)
        assert len(out) < 200
        assert "truncated" in out

    def test_write_file_creates_parents(self, sample_dir: Path) -> None:
        out = tools.write_file(str(sample_dir / "nested" / "deep" / "f.txt"), "content")
        assert "written 7 chars" in out
        assert (sample_dir / "nested" / "deep" / "f.txt").read_text(encoding="utf-8") == "content"

    def test_list_files(self, sample_dir: Path) -> None:
        out = tools.list_files(str(sample_dir))
        assert "alpha.txt" in out
        assert "sub/" in out

    def test_search_files_finds_pattern(self, sample_dir: Path) -> None:
        out = tools.search_files("pattern", str(sample_dir))
        assert "beta.md" in out
        assert "gamma.py" in out

    def test_search_no_match(self, sample_dir: Path) -> None:
        assert tools.search_files("zzz-not-there", str(sample_dir)) == "no matches"


class TestTerminal:
    def test_denied_by_default(self) -> None:
        assert "permission denied" in tools.run_command("echo hi")

    def test_allowed_runs_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tools, "permission_handler", lambda cmd: True)
        out = tools.run_command("echo hello")
        assert "hello" in out

    def test_handler_receives_command(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[str] = []
        monkeypatch.setattr(tools, "permission_handler", lambda cmd: seen.append(cmd) or True)
        tools.run_command("echo x")
        assert seen == ["echo x"]

    def test_timeout_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tools, "permission_handler", lambda cmd: True)
        out = tools.run_command("echo hi", timeout=0)
        assert "timed out" in out or "Error" in out


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
            "run_command",
            "http_get",
            "web_search",
            "current_time",
            "system_info",
        } <= names

    def test_every_tool_has_description_and_schema(self) -> None:
        for tool in tools.BUILTIN_TOOLS:
            assert tool.description
            assert tool.parameters is not None


class TestRunCommandExitCode:
    """Phase B.1: non-zero exit produces visible warning."""

    def test_exit_code_in_output(self) -> None:
        """When the command exits non-zero, output shows ⚠ exit=N."""
        from eaccode import tools
        from eaccode.permissions import PermissionManager

        old_handler = tools.permission_handler
        try:
            manager = PermissionManager()
            manager.ask_handler = lambda n, a: True
            tools.permission_handler = lambda cmd: True

            # Use `exit 1` as the command (POSIX-bash)
            result = tools.run_command("bash -c " + chr(34) + "exit 1" + chr(34), timeout=5)
            assert "⚠ exit=1" in result
            assert "non-zero" in result
        finally:
            tools.permission_handler = old_handler

    def test_success_no_warning(self) -> None:
        """When the command succeeds, no warning is added."""
        from eaccode import tools

        old_handler = tools.permission_handler
        try:
            tools.permission_handler = lambda cmd: True
            result = tools.run_command("echo hello", timeout=5)
            assert "hello" in result
            assert "⚠ exit=" not in result
        finally:
            tools.permission_handler = old_handler


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
