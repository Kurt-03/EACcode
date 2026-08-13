"""Tests for browser automation (Phase D6).

Real-browser tests use a local file:// page and skip when playwright or
its chromium build is unavailable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eaccode import browser
from eaccode.browser import BrowserError, BrowserSession

pytest.importorskip("playwright")


@pytest.fixture(scope="module")
def session() -> Any:
    session = BrowserSession()
    try:
        session._ensure()
    except BrowserError as exc:
        pytest.skip(f"chromium unavailable: {exc}")
    yield session
    session.close()


@pytest.fixture
def page_file(tmp_path: Path) -> str:
    target = tmp_path / "page.html"
    target.write_text(
        "<html><head><title>Testseite</title></head><body>"
        "<h1>Hallo Browser</h1>"
        "<input id='feld' type='text'>"
        "<button onclick=\"document.getElementById('feld').value='geklickt'\">"
        "Klick mich</button>"
        "</body></html>",
        encoding="utf-8",
    )
    return target.as_uri()


class TestSession:
    def test_navigate_and_extract(self, session: Any, page_file: str) -> None:
        out = session.navigate(page_file)
        assert "Testseite" in out
        text = session.extract("h1")
        assert "Hallo Browser" in text

    def test_type_and_click(self, session: Any, page_file: str) -> None:
        session.navigate(page_file)
        session.type_text("#feld", "getippt")
        session.click("button")
        text = session.extract("#feld")
        assert "geklickt" in text

    def test_status(self, session: Any, page_file: str) -> None:
        session.navigate(page_file)
        status = session.status()
        assert "Testseite" in status
        assert "page.html" in status

    def test_screenshot(self, session: Any, page_file: str, tmp_path: Path) -> None:
        session.navigate(page_file)
        shot = tmp_path / "shot.png"
        out = session.screenshot(str(shot))
        assert "saved" in out
        assert shot.exists()
        assert shot.stat().st_size > 100

    def test_extract_missing_selector(self, session: Any, page_file: str) -> None:
        session.navigate(page_file)
        assert "no element matches" in session.extract("#gibtsnicht")


class TestTools:
    def test_make_browser_tools(self) -> None:
        tools = {tool.name: tool for tool in browser.make_browser_tools()}
        assert set(tools) == {
            "browser_navigate",
            "browser_click",
            "browser_type",
            "browser_extract",
            "browser_screenshot",
            "browser_status",
        }

    def test_error_path_returns_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Broken:
            def navigate(self, url: str) -> str:
                raise BrowserError("playwright is not installed")

        monkeypatch.setattr(browser, "_session", Broken())
        tools = {tool.name: tool for tool in browser.make_browser_tools()}
        out = tools["browser_navigate"].func("https://example.com")
        assert "Error:" in out
        assert "playwright" in out
