"""Tests for the provider registry and family detection."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from eaccode.providers import registry
from eaccode.providers.anthropic import AnthropicProvider


@pytest.fixture(autouse=True)
def reset_registry_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the provider cache between tests."""
    registry.reset_cache()
    yield
    registry.reset_cache()


class TestFamilyDetection:
    """URL/name rules map a provider to an SDK family."""

    def test_anthropic_family_by_url(self) -> None:
        assert registry.detect_family(
            "minimax",
            {"base_url": "https://api.minimax.io/anthropic"},
        ) == "anthropic"

    def test_anthropic_family_by_url_with_v1(self) -> None:
        assert registry.detect_family(
            "minimax",
            {"base_url": "https://api.minimax.io/anthropic/v1"},
        ) == "anthropic"

    def test_anthropic_family_by_url_trail_slash(self) -> None:
        assert registry.detect_family(
            "minimax",
            {"base_url": "https://api.minimax.io/anthropic/"},
        ) == "anthropic"

    def test_anthropic_family_by_name(self) -> None:
        """Native Anthropic providers without base_url are recognized."""
        for name in ("anthropic", "minimax", "minimax-oauth", "minimax-cn"):
            assert registry.detect_family(name, {}) == "anthropic"

    def test_unsupported_family_for_unknown_provider(self) -> None:
        assert registry.detect_family(
            "openai",
            {"base_url": "https://api.openai.com/v1"},
        ) == "unsupported"

    def test_unsupported_family_for_ollama(self) -> None:
        assert registry.detect_family(
            "ollama", {"base_url": "http://localhost:11434"}
        ) == "unsupported"


class TestApiKeyResolution:
    """env wins over file for API keys."""

    def test_env_var_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "sk-from-env")
        assert registry._api_key_from_config({"api_key": "sk-from-file", "api_key_env": "MY_KEY"}) == "sk-from-env"

    def test_file_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MY_KEY", raising=False)
        assert registry._api_key_from_config({"api_key": "sk-from-file", "api_key_env": "MY_KEY"}) == "sk-from-file"

    def test_no_env_no_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MY_KEY", raising=False)
        assert registry._api_key_from_config({"api_key_env": "MY_KEY"}) == ""


class TestRegistryGet:
    """get() returns the right provider and caches it."""

    def test_minimax_returns_anthropic_provider(self) -> None:
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            provider = registry.get(
                "minimax",
                {
                    "base_url": "https://api.minimax.io/anthropic",
                    "api_key": "sk-fake",
                },
                model="minimax/MiniMax-M3",
            )
        assert isinstance(provider, AnthropicProvider)

    def test_native_anthropic_returns_anthropic_provider(self) -> None:
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            provider = registry.get(
                "anthropic",
                {"api_key": "sk-fake"},
                model="claude-sonnet-4-5",
            )
        assert isinstance(provider, AnthropicProvider)

    def test_unsupported_provider_raises(self) -> None:
        with pytest.raises(NotImplementedError) as exc_info:
            registry.get(
                "openai",
                {"base_url": "https://api.openai.com/v1", "api_key": "sk-fake"},
            )
        assert "openai" in str(exc_info.value).lower()

    def test_caches_by_provider_name_base_url_api_key(self) -> None:
        """Same provider name + base_url + api_key returns the same instance."""
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            p1 = registry.get(
                "minimax",
                {"base_url": "https://api.minimax.io/anthropic", "api_key": "sk-fake"},
                model="minimax/MiniMax-M3",
            )
            p2 = registry.get(
                "minimax",
                {"base_url": "https://api.minimax.io/anthropic", "api_key": "sk-fake"},
                model="minimax/MiniMax-M3",
            )
        assert p1 is p2

    def test_different_api_key_creates_new_provider(self) -> None:
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            p1 = registry.get(
                "minimax",
                {"base_url": "https://api.minimax.io/anthropic", "api_key": "sk-1"},
            )
            p2 = registry.get(
                "minimax",
                {"base_url": "https://api.minimax.io/anthropic", "api_key": "sk-2"},
            )
        assert p1 is not p2

    def test_env_api_key_picked_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MINIMAX_API_KEY", "sk-from-env")
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            provider = registry.get(
                "minimax",
                {"base_url": "https://api.minimax.io/anthropic", "api_key_env": "MINIMAX_API_KEY"},
            )
        assert isinstance(provider, AnthropicProvider)


class TestRegistryReset:
    def test_reset_cache_clears_providers(self) -> None:
        with patch.dict("sys.modules", {"anthropic": MagicMock()}):
            registry.get(
                "minimax",
                {"base_url": "https://api.minimax.io/anthropic", "api_key": "sk-1"},
            )
        assert len(registry._provider_cache) == 1
        registry.reset_cache()
        assert len(registry._provider_cache) == 0
