"""Provider registry: maps provider-name + config to a Provider instance.

Detection rules (Plan I P0.2):
- Anthropic-family: providers whose base_url ends with /anthropic.
- OpenAI-compat-family: providers whose base_url ends with /openai,
  contains /v1, or whose provider name is openai / openrouter / ollama /
  vllm / deepseek / groq / xai / opencode-zen / etc.

Caching: One Provider instance per (provider_name, base_url, api_key) triple.
Cache lives in module scope for the process lifetime.
"""

from __future__ import annotations

from typing import Any

from eaccode.providers.anthropic import AnthropicProvider
from eaccode.providers.base import Provider
from eaccode.providers.openai_compat import OpenAICompatProvider

_FAMILY_ANTHROPIC = "anthropic"
_FAMILY_OPENAI_COMPAT = "openai_compat"
_FAMILY_UNSUPPORTED = "unsupported"

# Provider names that strongly suggest OpenAI-compat even without explicit base_url.
_OPENAI_COMPAT_NAMES = frozenset({
    "openai", "openrouter", "ollama", "vllm", "deepseek", "groq", "xai",
    "opencode", "opencode-zen", "mistral", "cohere",
})


def detect_family(provider_name: str, provider_config: dict[str, Any]) -> str:
    """Map a provider to a family code."""
    base_url = (provider_config.get("base_url") or "").rstrip("/").lower()
    # Anthropic-family: URL contains /anthropic as a path segment, OR the
    # provider name itself is in the Anthropic-Messages list.
    if "/anthropic" in base_url.split("?")[0]:
        return _FAMILY_ANTHROPIC
    # OpenAI-compat: URL ends with /openai or contains /v1, or the provider
    # name is in the OpenAI-Compat list.
    if base_url.endswith("/openai") or "/v1" in base_url:
        return _FAMILY_OPENAI_COMPAT
    if provider_name in _OPENAI_COMPAT_NAMES:
        return _FAMILY_OPENAI_COMPAT
    if provider_name in {"anthropic", "minimax", "minimax-oauth", "minimax-cn"}:
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
    elif family == _FAMILY_OPENAI_COMPAT:
        provider: Provider = OpenAICompatProvider(
            name=provider_name,
            config=provider_config,
            model=model,
        )
    else:
        raise NotImplementedError(
            f"Provider {provider_name!r} uses family {family!r}. "
            "Neither Anthropic-Messages nor OpenAI-Chat-Completions "
            "are detected. Set a base_url ending in /anthropic or /openai "
            "(or one containing /v1)."
        )

    _provider_cache[cache_key] = provider
    return provider


def reset_cache() -> None:
    """Clear the provider cache. Used by tests."""
    _provider_cache.clear()
