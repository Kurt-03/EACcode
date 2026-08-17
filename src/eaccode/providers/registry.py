"""Provider registry: maps provider-name + config to a Provider instance.

Detection rules:
- Anthropic-family: providers whose base_url ends with /anthropic
  (e.g. native Anthropic, MiniMax, DeepSeek-Anthropic).
- Otherwise: not supported in the first cut (OpenAI compat is out of scope).

Caching: One Provider instance per (provider_name, base_url, api_key) triple.
Cache lives in module scope for the process lifetime.
"""

from __future__ import annotations

from typing import Any

from eaccode.providers.anthropic import AnthropicProvider
from eaccode.providers.base import Provider

_FAMILY_ANTHROPIC = "anthropic"
_FAMILY_UNSUPPORTED = "unsupported"


def detect_family(provider_name: str, provider_config: dict[str, Any]) -> str:
    """Map a provider to a family code (anthropic | unsupported)."""
    base_url = (provider_config.get("base_url") or "").rstrip("/").lower()
    if base_url.endswith("/anthropic"):
        return _FAMILY_ANTHROPIC
    if provider_name in {"anthropic", "minimax", "minimax-oauth", "minimax-cn"}:
        # No explicit base_url, but the provider name strongly suggests
        # Anthropic-Messages-compatible.
        return _FAMILY_ANTHROPIC
    return _FAMILY_UNSUPPORTED


def _api_key_from_config(provider_config: dict[str, Any]) -> str:
    """Resolve the API key from a provider config (env wins over file)."""
    import os

    env_var = provider_config.get("api_key_env")
    if env_var:
        env_value = os.environ.get(env_var)
        if env_value:
            return env_value
    file_value = provider_config.get("api_key")
    if isinstance(file_value, str) and file_value:
        return file_value
    return ""


# Cache: (provider_name, base_url, api_key) -> Provider
_provider_cache: dict[tuple[str, str, str], Provider] = {}


def get(
    provider_name: str,
    provider_config: dict[str, Any],
    *,
    model: str = "",
    timeout: float = 60.0,
) -> Provider:
    """Return a Provider instance for the given provider.

    Caches per (provider_name, base_url, api_key) so the same Provider
    is reused across requests within one process.
    """
    base_url = provider_config.get("base_url") or ""
    api_key = _api_key_from_config(provider_config)
    cache_key = (provider_name, base_url, api_key)
    if cache_key in _provider_cache:
        return _provider_cache[cache_key]

    family = detect_family(provider_name, provider_config)
    if family == _FAMILY_ANTHROPIC:
        provider: Provider = AnthropicProvider(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
        )
    else:
        raise NotImplementedError(
            f"Provider {provider_name!r} uses family {family!r}. "
            "Only Anthropic-Messages-compatible providers are supported "
            "in this build. OpenAI-compat adapters are out of scope."
        )

    _provider_cache[cache_key] = provider
    return provider


def reset_cache() -> None:
    """Clear the provider cache. Used by tests."""
    _provider_cache.clear()
