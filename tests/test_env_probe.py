"""Tests for env_probe (Phase G.6, Plan G v5)."""

from __future__ import annotations

import pytest

from eaccode import env_probe as ep


@pytest.fixture(autouse=True)
def _reset():
    ep._reset_cache_for_tests()
    yield
    ep._reset_cache_for_tests()


class TestProbeLine:
    def test_returns_non_empty_string(self) -> None:
        line = ep.get_environment_probe_line()
        assert isinstance(line, str)
        assert line.startswith("Environment probe:")

    def test_force_refresh(self) -> None:
        first = ep.get_environment_probe_line()
        ep._reset_cache_for_tests()
        second = ep.get_environment_probe_line()
        assert first == second


class TestProbeData:
    def test_returns_full_dict(self) -> None:
        data = ep.get_environment_data()
        for key in (
            "python", "pip", "pep668", "git", "npm", "cargo", "docker", "pytest"
        ):
            assert key in data

    def test_python_field_set(self) -> None:
        data = ep.get_environment_data()
        assert data["python"] is not None
        assert "Python" in data["python"]  # type: ignore[operator]

    def test_pip_yes_or_no(self) -> None:
        data = ep.get_environment_data()
        assert data["pip"] in ("yes", "no")


class TestCaching:
    def test_cache_hit_skips_subprocess(self, monkeypatch) -> None:
        call_count = [0]

        original_probe = ep._probe_python_version

        def counting_probe():
            call_count[0] += 1
            return original_probe()

        monkeypatch.setattr(ep, "_probe_python_version", counting_probe)
        # First call does the probe
        ep.get_environment_probe_line()
        first = call_count[0]
        # Subsequent calls use cache
        ep.get_environment_probe_line()
        ep.get_environment_probe_line()
        assert call_count[0] == first

    def test_force_refresh_runs_again(self, monkeypatch) -> None:
        call_count = [0]
        original = ep._probe_python_version

        def counting():
            call_count[0] += 1
            return original()

        monkeypatch.setattr(ep, "_probe_python_version", counting)
        ep.get_environment_probe_line()
        first = call_count[0]
        ep.get_environment_probe_line(force_refresh=True)
        assert call_count[0] > first


class TestAsyncWarm:
    def test_warm_is_idempotent(self) -> None:
        ep.warm_environment_probe_async()
        ep.warm_environment_probe_async()
        # Thread is alive or already finished - both states are valid.
