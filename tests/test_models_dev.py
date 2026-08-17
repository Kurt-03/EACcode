"""Tests for models.dev registry integration."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from eaccode import models_dev

# ---------------------------------------------------------------------------
# Sample registry fixture (mimics models.dev/api.json shape)
# ---------------------------------------------------------------------------

SAMPLE_REGISTRY: dict[str, Any] = {
    "minimax": {
        "name": "MiniMax (minimax.io)",
        "env": ["MINIMAX_API_KEY"],
        "api": "https://api.minimax.io/anthropic/v1",
        "doc": "https://platform.minimax.io/docs/guides/quickstart",
        "models": {
            "MiniMax-M3": {
                "name": "MiniMax-M3",
                "family": "minimax",
                "reasoning": True,
                "tool_call": True,
                "attachment": False,
                "temperature": True,
                "structured_output": True,
                "open_weights": False,
                "limit": {"context": 1000000, "output": 128000},
                "cost": {"input": 0.3, "output": 1.2},
                "modalities": {"input": ["text"], "output": ["text"]},
                "knowledge": "2025-08",
                "release_date": "2025-08",
                "status": "",
            },
            "MiniMax-M2.7": {
                "name": "MiniMax-M2.7",
                "family": "minimax",
                "reasoning": True,
                "tool_call": True,
                "attachment": False,
                "temperature": True,
                "structured_output": True,
                "open_weights": False,
                "limit": {"context": 204800, "output": 131072},
                "cost": {"input": 0.3, "output": 1.2},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
                "knowledge": "2025-04",
                "release_date": "2025-04",
                "status": "",
            },
        },
    },
    "anthropic": {
        "name": "Anthropic",
        "env": ["ANTHROPIC_API_KEY"],
        "api": "https://api.anthropic.com/v1",
        "doc": "https://docs.anthropic.com",
        "models": {
            "claude-sonnet-4-5": {
                "name": "Claude Sonnet 4.5",
                "family": "claude",
                "reasoning": True,
                "tool_call": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 200000, "output": 64000},
                "cost": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
            },
        },
    },
}


@pytest.fixture(autouse=True)
def reset_cache(tmp_path, monkeypatch):
    """Reset models.dev module-level state between tests.

    Reset cache state to defaults and redirect disk cache to tmp_path so
    no real disk writes happen during tests.
    """
    # Reset cache state
    monkeypatch.setattr(models_dev, "_models_dev_cache", {}, raising=False)
    monkeypatch.setattr(models_dev, "_models_dev_cache_time", 0.0, raising=False)
    monkeypatch.setattr(models_dev, "_models_dev_retry_after", 0.0, raising=False)
    monkeypatch.setattr(
        models_dev, "_models_dev_refresh_in_flight", False, raising=False
    )
    # Mock disk cache to tmp_path so no real disk writes happen
    monkeypatch.setattr(
        models_dev,
        "_get_cache_path",
        lambda: tmp_path / "models_dev_cache.json",
    )
    yield


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestDataclasses:
    """ModelInfo and ProviderInfo parsing."""

    def test_parse_model_info_minimax(self) -> None:
        raw = SAMPLE_REGISTRY["minimax"]["models"]["MiniMax-M3"]
        info = models_dev._parse_model_info("MiniMax-M3", raw, "minimax")
        assert info.id == "MiniMax-M3"
        assert info.family == "minimax"
        assert info.provider_id == "minimax"
        assert info.reasoning is True
        assert info.tool_call is True
        assert info.context_window == 1000000
        assert info.max_output == 128000
        assert info.cost_input == 0.3
        assert info.cost_output == 1.2
        assert info.cost_cache_read is None

    def test_parse_model_info_with_cache_pricing(self) -> None:
        raw = SAMPLE_REGISTRY["anthropic"]["models"]["claude-sonnet-4-5"]
        info = models_dev._parse_model_info("claude-sonnet-4-5", raw, "anthropic")
        assert info.cost_input == 3.0
        assert info.cost_output == 15.0
        assert info.cost_cache_read == 0.3
        assert info.attachment is True  # vision support

    def test_parse_provider_info(self) -> None:
        raw = SAMPLE_REGISTRY["minimax"]
        info = models_dev._parse_provider_info("minimax", raw)
        assert info.id == "minimax"
        assert info.name == "MiniMax (minimax.io)"
        assert info.env == ("MINIMAX_API_KEY",)
        assert info.api == "https://api.minimax.io/anthropic/v1"
        assert info.model_count == 2

    def test_model_info_supports_vision(self) -> None:
        raw = SAMPLE_REGISTRY["minimax"]["models"]["MiniMax-M2.7"]  # has image
        info = models_dev._parse_model_info("MiniMax-M2.7", raw, "minimax")
        assert info.supports_vision() is True

    def test_model_info_format_cost(self) -> None:
        raw = SAMPLE_REGISTRY["minimax"]["models"]["MiniMax-M3"]
        info = models_dev._parse_model_info("MiniMax-M3", raw, "minimax")
        assert info.format_cost() == "$0.30/M in, $1.20/M out"

    def test_model_info_format_capabilities(self) -> None:
        raw = SAMPLE_REGISTRY["minimax"]["models"]["MiniMax-M3"]
        info = models_dev._parse_model_info("MiniMax-M3", raw, "minimax")
        caps = info.format_capabilities()
        assert "reasoning" in caps
        assert "tools" in caps


class TestQueries:
    """Query the parsed models.dev registry."""

    def test_get_provider_info_found(self) -> None:
        with patch.object(
            models_dev, "fetch_models_dev", return_value=SAMPLE_REGISTRY
        ):
            info = models_dev.get_provider_info("minimax")
        assert info is not None
        assert info.name == "MiniMax (minimax.io)"
        assert info.model_count == 2

    def test_get_provider_info_not_found(self) -> None:
        with patch.object(
            models_dev, "fetch_models_dev", return_value=SAMPLE_REGISTRY
        ):
            info = models_dev.get_provider_info("nonexistent")
        assert info is None

    def test_get_model_info_found(self) -> None:
        with patch.object(
            models_dev, "fetch_models_dev", return_value=SAMPLE_REGISTRY
        ):
            info = models_dev.get_model_info("minimax", "MiniMax-M3")
        assert info is not None
        assert info.context_window == 1000000
        assert info.max_output == 128000

    def test_get_model_info_not_found(self) -> None:
        with patch.object(
            models_dev, "fetch_models_dev", return_value=SAMPLE_REGISTRY
        ):
            info = models_dev.get_model_info("minimax", "MiniMax-M99")
        assert info is None

    def test_list_provider_models(self) -> None:
        with patch.object(
            models_dev, "fetch_models_dev", return_value=SAMPLE_REGISTRY
        ):
            models = models_dev.list_provider_models("minimax")
        assert models == ["MiniMax-M2.7", "MiniMax-M3"]

    def test_list_agentic_models_filters(self) -> None:
        # Inject a non-agentic model that should be filtered out
        registry = dict(SAMPLE_REGISTRY)
        registry["minimax"]["models"]["no-tools-model"] = {
            "name": "No Tools",
            "family": "minimax",
            "reasoning": False,
            "tool_call": False,
            "limit": {"context": 100, "output": 100},
            "cost": {"input": 0.1, "output": 0.2},
            "modalities": {"input": ["text"], "output": ["text"]},
        }
        with patch.object(models_dev, "fetch_models_dev", return_value=registry):
            models = models_dev.list_agentic_models("minimax")
        assert "no-tools-model" not in models
        assert "MiniMax-M3" in models

    def test_convenience_helpers(self) -> None:
        with patch.object(
            models_dev, "fetch_models_dev", return_value=SAMPLE_REGISTRY
        ):
            assert models_dev.get_max_output_tokens("minimax", "MiniMax-M3") == 128000
            assert models_dev.get_context_window("minimax", "MiniMax-M3") == 1000000
            assert models_dev.get_max_output_tokens("minimax", "unknown") == 0


class TestCacheHierarchy:
    """In-memory → disk → network cache hierarchy."""

    def test_fresh_in_memory_returns_immediately(self) -> None:
        models_dev._models_dev_cache = SAMPLE_REGISTRY
        models_dev._models_dev_cache_time = time.time()
        with patch.object(
            models_dev, "_fetch_models_dev_from_network"
        ) as mock_fetch:
            models_dev.fetch_models_dev()
        mock_fetch.assert_not_called()

    def test_stale_in_memory_triggers_background_refresh(self) -> None:
        models_dev._models_dev_cache = SAMPLE_REGISTRY
        # 2 hours old — stale
        models_dev._models_dev_cache_time = time.time() - 7200
        # Patch both the start function AND the network fetch so the
        # background thread (if it spawns) doesn't leak real network
        # calls into subsequent tests.
        with patch.object(
            models_dev, "_start_background_refresh_models_dev"
        ) as mock_bg, patch.object(
            models_dev, "_fetch_models_dev_from_network"
        ):
            models_dev.fetch_models_dev()
        mock_bg.assert_called_once()
        # Background does NOT block — returns stale data immediately
        assert models_dev._models_dev_cache == SAMPLE_REGISTRY

    def test_stale_in_memory_does_not_call_network(self) -> None:
        """Stale cache returns immediately and never touches network."""
        models_dev._models_dev_cache = SAMPLE_REGISTRY
        models_dev._models_dev_cache_time = time.time() - 7200
        with patch.object(
            models_dev, "_fetch_models_dev_from_network"
        ) as mock_fetch, patch.object(
            models_dev, "_start_background_refresh_models_dev"
        ):
            data = models_dev.fetch_models_dev()
        # Should not block — returns stale data
        assert data == SAMPLE_REGISTRY
        # Background refresh was triggered, but network was NOT called
        # directly during fetch_models_dev (only the background thread
        # would call it, and that thread is mocked out)
        mock_fetch.assert_not_called()

    def test_empty_cache_falls_through_to_network(self) -> None:
        with patch.object(
            models_dev,
            "_fetch_models_dev_from_network",
            return_value=SAMPLE_REGISTRY,
        ) as mock_fetch:
            data = models_dev.fetch_models_dev()
        mock_fetch.assert_called_once()
        assert data == SAMPLE_REGISTRY

    def test_empty_cache_disk_fallback(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "models_dev_cache.json"
        cache_file.write_text(json.dumps(SAMPLE_REGISTRY), encoding="utf-8")
        # Override the fixture's _get_cache_path with our local cache_file
        orig_get_cache_path = models_dev._get_cache_path
        models_dev._get_cache_path = lambda: cache_file
        try:
            # Patch both network fetch AND background refresh trigger:
            # Path 3 (disk hit) starts a background refresh, which would
            # otherwise call the real network.
            with patch.object(
                models_dev, "_fetch_models_dev_from_network"
            ) as mock_fetch, patch.object(
                models_dev, "_start_background_refresh_models_dev"
            ) as mock_bg_refresh:
                data = models_dev.fetch_models_dev()
            mock_fetch.assert_not_called()
            mock_bg_refresh.assert_called_once()
            assert data == SAMPLE_REGISTRY
        finally:
            models_dev._get_cache_path = orig_get_cache_path

    def test_allow_network_false_uses_cache_only(self) -> None:
        models_dev._models_dev_cache = SAMPLE_REGISTRY
        models_dev._models_dev_cache_time = 0.0  # irrelevant when allow_network=False
        # Disk cache is redirected to tmp_path by fixture. Need to make
        # sure it does NOT contain SAMPLE_REGISTRY, so the in-memory cache
        # is used.
        with patch.object(
            models_dev, "_fetch_models_dev_from_network"
        ) as mock_fetch:
            data = models_dev.fetch_models_dev(allow_network=False)
        mock_fetch.assert_not_called()
        assert data == SAMPLE_REGISTRY

    def test_allow_network_false_no_cache_returns_empty(self) -> None:
        with patch.object(
            models_dev, "_fetch_models_dev_from_network"
        ) as mock_fetch:
            data = models_dev.fetch_models_dev(allow_network=False)
        mock_fetch.assert_not_called()
        assert data == {}


class TestForceRefresh:
    """force_refresh=True bypasses cache and tries network."""

    def test_force_refresh_success(self) -> None:
        models_dev._models_dev_cache = {"old": "data"}
        models_dev._models_dev_cache_time = time.time()
        new_registry = {"fresh": "data"}
        # Mock both network fetch AND disk save (fixture redirects path
        # to tmp_path, but we don't want disk writes leaking either)
        with patch.object(
            models_dev,
            "_fetch_models_dev_from_network",
            return_value=new_registry,
        ) as mock_fetch, patch.object(
            models_dev, "_save_disk_cache"
        ):
            data = models_dev.fetch_models_dev(force_refresh=True)
        mock_fetch.assert_called_once()
        assert data == new_registry
        assert models_dev._models_dev_cache == new_registry

    def test_force_refresh_failure_falls_back_to_cache(self) -> None:
        models_dev._models_dev_cache = SAMPLE_REGISTRY
        models_dev._models_dev_cache_time = time.time()
        with patch.object(
            models_dev,
            "_fetch_models_dev_from_network",
            side_effect=ConnectionError("network down"),
        ):
            data = models_dev.fetch_models_dev(force_refresh=True)
        assert data == SAMPLE_REGISTRY


class TestDiskCache:
    """Disk cache save/load roundtrip."""

    def test_disk_cache_save_and_load(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "models_dev_cache.json"
        orig_get_cache_path = models_dev._get_cache_path
        models_dev._get_cache_path = lambda: cache_file
        try:
            models_dev._save_disk_cache(SAMPLE_REGISTRY)
            assert cache_file.exists()
            loaded = models_dev._load_disk_cache()
            assert loaded == SAMPLE_REGISTRY
        finally:
            models_dev._get_cache_path = orig_get_cache_path

    def test_disk_cache_load_missing_returns_empty(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "does_not_exist.json"
        orig_get_cache_path = models_dev._get_cache_path
        models_dev._get_cache_path = lambda: cache_file
        try:
            loaded = models_dev._load_disk_cache()
            assert loaded == {}
        finally:
            models_dev._get_cache_path = orig_get_cache_path

    def test_disk_cache_age_seconds(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "models_dev_cache.json"
        cache_file.write_text("{}", encoding="utf-8")
        orig_get_cache_path = models_dev._get_cache_path
        models_dev._get_cache_path = lambda: cache_file
        try:
            age = models_dev._disk_cache_age_seconds()
            assert age is not None
            assert age >= 0  # just-created, very fresh
        finally:
            models_dev._get_cache_path = orig_get_cache_path


class TestNetworkErrorHandling:
    """Refresh failures are noted and rate-limited."""

    def test_network_failure_arms_backoff(self) -> None:
        with patch.object(
            models_dev,
            "_fetch_models_dev_from_network",
            side_effect=ConnectionError("network down"),
        ):
            data = models_dev.fetch_models_dev()
        assert data == {}
        assert models_dev._models_dev_retry_after > time.time()

    def test_backoff_suppresses_background_refresh(self) -> None:
        models_dev._models_dev_retry_after = time.time() + 300  # 5 min
        with patch.object(models_dev, "threading") as mock_threading:
            models_dev._start_background_refresh_models_dev()
        mock_threading.Thread.assert_not_called()
