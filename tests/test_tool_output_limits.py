"""Tests for tool_output_limits (Phase G.12, Plan G v5)."""

from __future__ import annotations

import pytest

from eaccode import tool_output_limits as tol


@pytest.fixture(autouse=True)
def _reset_cache():
    tol._reset_tool_output_limits_cache()
    yield
    tol._reset_tool_output_limits_cache()


class TestDefaults:
    def test_returns_defaults_when_no_config(self, monkeypatch) -> None:
        from eaccode import config as cfg

        monkeypatch.setattr(cfg, "load_config", lambda: None)
        limits = tol.get_tool_output_limits()
        assert limits == {
            "max_bytes": tol.DEFAULT_MAX_BYTES,
            "max_lines": tol.DEFAULT_MAX_LINES,
            "max_line_length": tol.DEFAULT_MAX_LINE_LENGTH,
        }

    def test_defaults_constants(self) -> None:
        assert tol.DEFAULT_MAX_BYTES == 50_000
        assert tol.DEFAULT_MAX_LINES == 2000
        assert tol.DEFAULT_MAX_LINE_LENGTH == 2000


class TestConfigOverride:
    def test_reads_from_config(self, monkeypatch) -> None:
        from eaccode import config as cfg

        monkeypatch.setattr(
            cfg,
            "load_config",
            lambda: {"tool_output": {"max_bytes": 100000, "max_lines": 5000}},
        )
        limits = tol.get_tool_output_limits()
        assert limits["max_bytes"] == 100000
        assert limits["max_lines"] == 5000
        assert limits["max_line_length"] == tol.DEFAULT_MAX_LINE_LENGTH


class TestCoercion:
    def test_negative_falls_back(self, monkeypatch) -> None:
        from eaccode import config as cfg

        monkeypatch.setattr(
            cfg, "load_config", lambda: {"tool_output": {"max_bytes": -1}}
        )
        limits = tol.get_tool_output_limits()
        assert limits["max_bytes"] == tol.DEFAULT_MAX_BYTES

    def test_string_parses(self, monkeypatch) -> None:
        from eaccode import config as cfg

        monkeypatch.setattr(
            cfg, "load_config", lambda: {"tool_output": {"max_lines": "9999"}}
        )
        limits = tol.get_tool_output_limits()
        assert limits["max_lines"] == 9999

    def test_invalid_string_falls_back(self, monkeypatch) -> None:
        from eaccode import config as cfg

        monkeypatch.setattr(
            cfg, "load_config", lambda: {"tool_output": {"max_lines": "abc"}}
        )
        limits = tol.get_tool_output_limits()
        assert limits["max_lines"] == tol.DEFAULT_MAX_LINES


class TestShortcuts:
    def test_individual_getters(self, monkeypatch) -> None:
        from eaccode import config as cfg

        monkeypatch.setattr(
            cfg, "load_config", lambda: {"tool_output": {"max_bytes": 12345}}
        )
        assert tol.get_max_bytes() == 12345
        assert tol.get_max_lines() == tol.DEFAULT_MAX_LINES
        assert tol.get_max_line_length() == tol.DEFAULT_MAX_LINE_LENGTH


class TestCaching:
    def test_cache_repeated_calls(self, monkeypatch) -> None:
        from eaccode import config as cfg

        calls = [0]
        original_load = cfg.load_config

        def tracking_load():
            calls[0] += 1
            return {"tool_output": {"max_bytes": 7777}}

        monkeypatch.setattr(cfg, "load_config", tracking_load)
        # First call loads
        tol.get_tool_output_limits()
        first = calls[0]
        # Subsequent calls use cache
        tol.get_tool_output_limits()
        tol.get_tool_output_limits()
        assert calls[0] == first

    def test_reset_cache_forces_reload(self, monkeypatch) -> None:
        from eaccode import config as cfg

        monkeypatch.setattr(cfg, "load_config", lambda: {"tool_output": {}})
        tol.get_tool_output_limits()
        tol._reset_tool_output_limits_cache()
        # After reset, next call will hit config again
        limits = tol.get_tool_output_limits()
        assert "max_bytes" in limits
