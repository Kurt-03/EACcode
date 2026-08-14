"""Tests for the startup banner (Hermes style)."""

from __future__ import annotations

from typing import Any

import pytest

from eaccode import banner

CONF: dict[str, Any] = {
    "model": {"default": "minimax/MiniMax-M3"},
    "mcp": {
        "servers": {
            "Roblox_Studio": {"command": "cmd.exe", "transport": "stdio"},
        }
    },
}


class TestModelLabel:
    def test_splits_provider_and_name(self) -> None:
        assert banner.model_label(CONF) == "MiniMax-M3 (minimax)"

    def test_plain_default(self) -> None:
        assert banner.model_label({"model": {"default": "gpt-4o"}}) == "gpt-4o"

    def test_missing(self) -> None:
        assert banner.model_label({}) == "--"


class TestRenderBanner:
    def test_contains_logo_version_and_model(self) -> None:
        text = banner.render_banner(CONF, session_id="s1", cwd="C:\\x")
        assert "███████╗" in text  # logo block
        assert "eaccode 0.0.1" in text
        assert "MiniMax-M3 (minimax)" in text
        assert "C:\\x" in text

    def test_contains_status_sections(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(banner, "count_skills", lambda: 3)
        text = banner.render_banner(CONF, session_id="s1")
        assert "Session: s1" in text
        assert "Available Tools:" in text
        assert "Roblox_Studio" in text  # MCP servers listed
        assert "Available Skills:" in text
        assert "/help for commands" in text

    def test_box_uses_rounded_corners(self) -> None:
        text = banner.render_banner(CONF)
        assert "╭─" in text
        assert "╰─" in text
        assert "│" in text

    def test_welcome_and_tip(self) -> None:
        text = banner.render_banner(CONF)
        assert "Welcome to eaccode!" in text
        assert "✦ Tip:" in text

    def test_session_placeholder(self) -> None:
        assert "Session: --" in banner.render_banner(CONF)

    def test_no_mcp_omits_section(self) -> None:
        text = banner.render_banner({"model": {}})
        assert "MCP Servers" not in text


class TestCounts:
    def test_tools_positive(self) -> None:
        assert banner.count_tools() > 10

    def test_skills_non_negative(self) -> None:
        assert banner.count_skills() >= 0


class TestStatusLine:
    def test_ready(self) -> None:
        assert banner.status_line("MiniMax-M3") == "⚕ MiniMax-M3 │ ready"

    def test_with_stats(self) -> None:
        line = banner.status_line("MiniMax-M3", seconds=2.5, chars=100)
        assert "2.5s" in line
        assert "100 chars" in line


def test_quiet_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EACCODE_QUIET", raising=False)
    assert not banner.quiet()
    monkeypatch.setenv("EACCODE_QUIET", "1")
    assert banner.quiet()
