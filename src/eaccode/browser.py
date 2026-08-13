"""Browser automation (Phase D6): Playwright-based navigation tools.

One shared browser session per process (lazy launch, thread-safe via lock).
Tools: navigate, click, type, extract, screenshot, status. The session
persists across calls, so the agent can browse multi-step.

Requires: playwright installed AND `playwright install chromium` once.
"""

from __future__ import annotations

import atexit
import contextlib
import threading
from pathlib import Path
from typing import Any

from eaccode.agent import Tool

NAV_TIMEOUT = 30_000


class BrowserError(Exception):
    """Raised for browser setup or action failures."""


class BrowserSession:
    """Shared headless Chromium session (lazy, locked, persistent)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

    def _ensure(self) -> Any:
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserError(
                "playwright is not installed - run: uv add playwright && "
                "playwright install chromium"
            ) from exc
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self._context = self._browser.new_context(viewport={"width": 1280, "height": 800})
            self._page = self._context.new_page()
        except Exception as exc:
            raise BrowserError(
                f"cannot launch chromium (run 'playwright install chromium'): {exc}"
            ) from exc
        return self._page

    def navigate(self, url: str) -> str:
        with self._lock:
            page = self._ensure()
            page.goto(url, timeout=NAV_TIMEOUT, wait_until="domcontentloaded")
            return f"title: {page.title()}\nurl: {page.url}"

    def click(self, selector: str) -> str:
        with self._lock:
            page = self._ensure()
            page.click(selector, timeout=NAV_TIMEOUT)
            return f"clicked {selector} -> url: {page.url}"

    def type_text(self, selector: str, text: str) -> str:
        with self._lock:
            page = self._ensure()
            page.fill(selector, text)
            return f"typed into {selector}"

    def extract(self, selector: str = "body") -> str:
        with self._lock:
            page = self._ensure()
            elements = page.query_selector_all(selector)
            if not elements:
                return f"(no element matches: {selector})"
            parts: list[str] = []
            for element in elements[:5]:
                tag = element.evaluate("e => e.tagName").lower()
                if tag == "input" or tag == "textarea":
                    parts.append(element.input_value())
                else:
                    parts.append((element.inner_text() or "").strip())
            return "\n".join(part for part in parts if part)

    def screenshot(self, path: str) -> str:
        with self._lock:
            page = self._ensure()
            target = Path(path).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target), full_page=True)
            return f"screenshot saved: {target}"

    def status(self) -> str:
        with self._lock:
            if self._page is None:
                return "(browser not started yet)"
            return f"url: {self._page.url}\ntitle: {self._page.title()}"

    def close(self) -> None:
        with self._lock:
            if self._browser is not None:
                with contextlib.suppress(Exception):
                    self._browser.close()
            if self._playwright is not None:
                with contextlib.suppress(Exception):
                    self._playwright.stop()
            self._browser = None
            self._context = None
            self._page = None
            self._playwright = None


_session = BrowserSession()
atexit.register(_session.close)


def _tool_navigate(url: str) -> str:
    try:
        return _session.navigate(url)
    except BrowserError as exc:
        return f"Error: {exc}"


def _tool_click(selector: str) -> str:
    try:
        return _session.click(selector)
    except BrowserError as exc:
        return f"Error: {exc}"


def _tool_type(selector: str, text: str) -> str:
    try:
        return _session.type_text(selector, text)
    except BrowserError as exc:
        return f"Error: {exc}"


def _tool_extract(selector: str = "body") -> str:
    try:
        return _session.extract(selector)
    except BrowserError as exc:
        return f"Error: {exc}"


def _tool_screenshot(path: str) -> str:
    try:
        return _session.screenshot(path)
    except BrowserError as exc:
        return f"Error: {exc}"


def _tool_status() -> str:
    try:
        return _session.status()
    except BrowserError as exc:
        return f"Error: {exc}"


def make_browser_tools() -> list[Tool]:
    """Agent tools for browser automation (D6)."""
    return [
        Tool(
            "browser_navigate",
            "Open a URL in the shared browser; returns the page title and url.",
            _tool_navigate,
            {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        ),
        Tool(
            "browser_click",
            "Click an element (CSS selector) on the current page.",
            _tool_click,
            {
                "type": "object",
                "properties": {"selector": {"type": "string"}},
                "required": ["selector"],
            },
        ),
        Tool(
            "browser_type",
            "Type text into an input field (CSS selector).",
            _tool_type,
            {
                "type": "object",
                "properties": {
                    "selector": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["selector", "text"],
            },
        ),
        Tool(
            "browser_extract",
            "Extract text from the page (default: whole body, max 5 elements).",
            _tool_extract,
            {
                "type": "object",
                "properties": {"selector": {"type": "string"}},
            },
        ),
        Tool(
            "browser_screenshot",
            "Save a full-page screenshot to a file path.",
            _tool_screenshot,
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        ),
        Tool(
            "browser_status",
            "Show the current url and title of the shared browser session.",
            _tool_status,
            {"type": "object", "properties": {}},
        ),
    ]
