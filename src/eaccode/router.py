"""Model router: provider registry, model catalog, live pings and fallback chain.

Phase A3: BYOK — all keys stay on the user's machine. Every provider is
configured in config.yaml (``providers``); model ids use LiteLLM syntax
(``provider/model``).
"""

from __future__ import annotations

import os
from typing import Any

from eaccode import config as cfg

# Model catalog: well-known model ids per provider (UX aid, not exhaustive).
KNOWN_MODELS: dict[str, list[str]] = {
    "openrouter": [
        "openrouter/anthropic/claude-sonnet-4",
        "openrouter/anthropic/claude-opus-4",
        "openrouter/meta-llama/llama-3.3-70b",
        "openrouter/deepseek/deepseek-chat",
    ],
    "anthropic": ["anthropic/claude-sonnet-4", "anthropic/claude-opus-4"],
    "openai": ["openai/gpt-4o", "openai/gpt-4o-mini"],
    "google": ["gemini/gemini-1.5-pro", "gemini/gemini-1.5-flash"],
    "xai": ["xai/grok-2"],
    "deepseek": ["deepseek/deepseek-chat"],
    "minimax": ["minimax/minimax-text-01"],
    "ollama": ["ollama/llama3.2", "ollama/qwen2.5"],
    "vllm": [],
    "lmstudio": [],
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


def _extract_text(response: Any) -> str:
    """Pull the reply text out of a LiteLLM completion response."""
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        return str(response)


def completion_response(
    model_id: str,
    messages: list[dict[str, str]],
    conf: dict[str, Any],
    timeout: float = 60.0,
    extra_kwargs: dict[str, Any] | None = None,
) -> Any:
    """One completion call; returns the raw LiteLLM response.

    ``extra_kwargs`` are forwarded to LiteLLM (e.g. tools, max_tokens).
    """
    provider_name = model_id.split("/", 1)[0]
    provider = (conf.get("providers") or {}).get(provider_name)
    api_key = resolve_api_key(provider)
    kwargs: dict[str, Any] = {"model": model_id, "messages": messages, "timeout": timeout}
    if extra_kwargs:
        kwargs.update(extra_kwargs)
    if api_key:
        kwargs["api_key"] = api_key
    if provider and provider.get("base_url"):
        kwargs["api_base"] = provider["base_url"]
    try:
        from litellm import completion

        return completion(**kwargs)
    except Exception as exc:  # litellm raises a broad family of exceptions
        raise ModelError(f"model call failed ({model_id}): {exc}") from exc


def completion_text(
    model_id: str,
    messages: list[dict[str, str]],
    conf: dict[str, Any],
    timeout: float = 60.0,
    extra_kwargs: dict[str, Any] | None = None,
) -> str:
    """One completion call; returns the extracted reply text."""
    response = completion_response(model_id, messages, conf, timeout, extra_kwargs)
    return _extract_text(response)


def call_model(
    conf: dict[str, Any],
    messages: list[dict[str, str]],
    model_id: str | None = None,
    timeout: float = 60.0,
) -> str:
    """Call the default model, then fall back through the chain.

    Raises ModelError when no model is configured or every call failed.
    """
    chain = [model_id] if model_id else model_chain(conf)
    if not chain:
        raise ModelError("no default model configured - run 'model set-default <model>'")
    last_error: Exception | None = None
    for candidate in chain:
        try:
            return completion_text(candidate, messages, conf, timeout)
        except ModelError as exc:
            last_error = exc
    raise ModelError(
        f"all models failed ({', '.join(chain)}): {last_error}"
    ) from last_error


def ping_model(
    model_id: str,
    conf: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> str:
    """Send a minimal live call; returns the model's reply (expected: 'pong')."""
    conf = conf or cfg.load_config()
    return call_model(
        conf, [{"role": "user", "content": PING_PROMPT}], model_id=model_id, timeout=timeout
    )
