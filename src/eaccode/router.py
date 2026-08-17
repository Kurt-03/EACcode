"""DEPRECATED — kept for back-compat. Use eaccode.providers instead.

This module is a thin shim over the new provider registry. New code should
import from:

    from eaccode.providers import registry as providers
    from eaccode.providers.base import StreamChunk, ToolCall

The old LiteLLM-based helpers (``completion_response``, ``stream_completion``,
``completion_text``, ``call_model``, ``ping_model``) have been replaced by
the typed provider adapters. The few legacy helpers still in use
(``all_model_ids``, ``model_chain``, ``provider_names``, ``ModelError``)
are stubbed here so external commands keep working.
"""

from __future__ import annotations

import os
from typing import Any

# Model catalog: well-known model ids per provider (UX aid, not exhaustive).
# For real catalog data, use eaccode.models_dev.
KNOWN_MODELS: dict[str, list[str]] = {
    "anthropic": ["anthropic/claude-sonnet-4", "anthropic/claude-opus-4"],
    "minimax": [
        "minimax/MiniMax-M3",
        "minimax/MiniMax-M2.5",
        "minimax/MiniMax-M2.1",
        "minimax/MiniMax-M2.1-lightning",
    ],
}

PING_PROMPT = "Reply with exactly: pong"


class ModelError(Exception):
    """Raised when a model call fails (network, auth, parsing, ...)."""


def resolve_api_key(provider: dict[str, Any] | None) -> str | None:
    """Return the api key for a provider config (env wins over file)."""
    provider = provider or {}
    env_var = provider.get("api_key_env")
    if env_var:
        value = os.environ.get(env_var)
        if value:
            return value
    return provider.get("api_key")


def provider_names(conf: dict[str, Any]) -> list[str]:
    """Sorted list of configured provider names."""
    return sorted((conf.get("providers") or {}).keys())


def model_chain(conf: dict[str, Any]) -> list[str]:
    """Default model followed by the fallback chain."""
    model = conf.get("model") or {}
    chain: list[str] = []
    if model.get("default"):
        chain.append(model["default"])
    chain.extend(model.get("fallback") or [])
    return chain


def all_model_ids(conf: dict[str, Any]) -> list[str]:
    """Every model id known to eaccode: chain, catalog and custom models."""
    ids: list[str] = []
    ids.extend(model_chain(conf))
    for name, provider in (conf.get("providers") or {}).items():
        ids.extend(KNOWN_MODELS.get(name, []))
        ids.extend(provider.get("models") or [])
    seen: set[str] = set()
    unique: list[str] = []
    for model_id in ids:
        if model_id and model_id not in seen:
            seen.add(model_id)
            unique.append(model_id)
    return unique


# ---------------------------------------------------------------------------
# Removed LiteLLM-based helpers — kept as raising shims so direct callers
# get a clear error pointing them at the new provider registry.
# ---------------------------------------------------------------------------


def _removed(_name: str) -> Any:
    raise ModelError(
        f"{_name}() was removed when LiteLLM was replaced by the "
        "Anthropic provider registry. Use 'provider registry' "
        "(eaccode.providers.registry.get) and StreamChunk iterators instead."
    )


def completion_response(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
    _removed("completion_response")


def stream_completion(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
    _removed("stream_completion")


def completion_text(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
    _removed("completion_text")


def call_model(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
    _removed("call_model")


def ping_model(*args: Any, **kwargs: Any) -> Any:  # pragma: no cover
    _removed("ping_model")
