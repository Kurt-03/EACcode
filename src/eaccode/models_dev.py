"""Models.dev registry integration for eaccode.

Fetches from https://models.dev/api.json — a community-maintained database
of 4000+ models across 109+ providers. Provides:

- Provider metadata: name, base URL, env vars, documentation link
- Model metadata: context window, max output, cost per million tokens,
  capabilities (reasoning, tool_call, vision, attachment), modalities,
  knowledge cutoff, open-weights flag, family, deprecation status

Data resolution order (mirrors Hermes models_dev.py):
  1. In-memory cache (fresh, or stale served immediately while a single
     background daemon thread refreshes)
  2. Disk cache (~/.local/eaccode/models_dev_cache.json — any age; stale
     data is served rather than blocking callers on the network)
  3. Network fetch (https://models.dev/api.json) — only when no cache
     exists at all; failed refreshes back off for 5 minutes process-wide

Other modules should import the dataclasses and query functions from here
rather than parsing the raw JSON themselves.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from eaccode import config

logger = logging.getLogger(__name__)

MODELS_DEV_URL = "https://models.dev/api.json"
_MODELS_DEV_CACHE_TTL = 3600  # 1 hour in-memory
_MODELS_DEV_RETRY_DELAY = 300  # 5 minutes after a failed refresh
_REQUEST_TIMEOUT = (5, 10)  # (connect, read) — fail fast on connect

# In-memory cache
_models_dev_cache: dict[str, Any] = {}
_models_dev_cache_time: float = 0.0
_models_dev_retry_after: float = 0.0
_models_dev_fetch_lock = threading.Lock()
_models_dev_refresh_lock = threading.Lock()
_models_dev_refresh_in_flight = False


# ---------------------------------------------------------------------------
# Dataclasses — rich metadata for providers and models
# ---------------------------------------------------------------------------


@dataclass
class ModelInfo:
    """Full metadata for a single model from models.dev."""

    id: str
    name: str
    family: str
    provider_id: str  # models.dev provider ID (e.g. "minimax")

    # Capabilities
    reasoning: bool = False
    tool_call: bool = False
    attachment: bool = False  # supports image/file attachments (vision)
    temperature: bool = False
    structured_output: bool = False
    open_weights: bool = False

    # Modalities
    input_modalities: tuple[str, ...] = ()
    output_modalities: tuple[str, ...] = ()

    # Limits
    context_window: int = 0
    max_output: int = 0

    # Cost (per million tokens, USD)
    cost_input: float = 0.0
    cost_output: float = 0.0
    cost_cache_read: float | None = None
    cost_cache_write: float | None = None

    # Metadata
    knowledge_cutoff: str = ""
    release_date: str = ""
    status: str = ""  # "alpha", "beta", "deprecated", or ""

    def has_cost_data(self) -> bool:
        return self.cost_input > 0 or self.cost_output > 0

    def supports_vision(self) -> bool:
        return self.attachment or "image" in self.input_modalities

    def supports_attachment(self) -> bool:
        return self.attachment

    def supports_pdf(self) -> bool:
        return "pdf" in self.input_modalities

    def supports_audio_input(self) -> bool:
        return "audio" in self.input_modalities

    def format_cost(self) -> str:
        if not self.has_cost_data():
            return "unknown"
        parts = [f"${self.cost_input:.2f}/M in", f"${self.cost_output:.2f}/M out"]
        if self.cost_cache_read is not None:
            parts.append(f"cache read ${self.cost_cache_read:.2f}/M")
        return ", ".join(parts)

    def format_capabilities(self) -> str:
        caps = []
        if self.reasoning:
            caps.append("reasoning")
        if self.tool_call:
            caps.append("tools")
        if self.supports_vision():
            caps.append("vision")
        if self.supports_pdf():
            caps.append("PDF")
        if self.supports_audio_input():
            caps.append("audio")
        if self.structured_output:
            caps.append("structured output")
        if self.open_weights:
            caps.append("open weights")
        return ", ".join(caps) if caps else "basic"


@dataclass
class ProviderInfo:
    """Full metadata for a provider from models.dev."""

    id: str  # models.dev provider ID
    name: str  # display name
    env: tuple[str, ...] = ()  # env var names for API key
    api: str = ""  # base URL
    doc: str = ""  # documentation URL
    model_count: int = 0


# ---------------------------------------------------------------------------
# Network + disk cache
# ---------------------------------------------------------------------------


def _get_cache_path() -> Path:
    """Return path to disk cache file."""
    return config.data_dir() / "models_dev_cache.json"


def _load_disk_cache() -> dict[str, Any]:
    """Load models.dev data from disk cache."""
    try:
        cache_path = _get_cache_path()
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug("Failed to load models.dev disk cache: %s", e)
    return {}


def _disk_cache_age_seconds() -> float | None:
    """Return age (in seconds) of the disk cache file, or None if missing."""
    try:
        cache_path = _get_cache_path()
        if not cache_path.exists():
            return None
        mtime = cache_path.stat().st_mtime
        age = time.time() - mtime
        # Negative age means clock skew — treat as unknown freshness.
        if age < 0:
            return None
        return age
    except Exception as e:
        logger.debug("Failed to stat models.dev disk cache: %s", e)
    return None


def _save_disk_cache(data: dict[str, Any]) -> None:
    """Save models.dev data to disk cache atomically."""
    try:
        cache_path = _get_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.debug("Failed to save models.dev disk cache: %s", e)


def _fetch_models_dev_from_network() -> dict[str, Any]:
    """Fetch the live models.dev registry without touching local caches.

    Raises on network errors and on an empty/invalid registry payload.
    """
    response = requests.get(MODELS_DEV_URL, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not data:
        raise ValueError("models.dev returned an empty or invalid registry")
    return data


def _commit_registry(data: dict[str, Any], *, where: str) -> None:
    """Persist a freshly fetched registry: disk + in-mem + clear backoff."""
    global _models_dev_cache, _models_dev_cache_time, _models_dev_retry_after
    _save_disk_cache(data)
    _models_dev_cache = data
    _models_dev_cache_time = time.time()
    _models_dev_retry_after = 0.0
    logger.debug(
        "Refreshed models.dev registry (%s): %d providers, %d total models",
        where,
        len(data),
        sum(len(p.get("models", {})) for p in data.values() if isinstance(p, dict)),
    )


def _note_refresh_failure(exc: Exception, *, where: str) -> None:
    """Record a failed refresh: arm the process-wide 5-minute backoff."""
    global _models_dev_retry_after
    _models_dev_retry_after = time.time() + _MODELS_DEV_RETRY_DELAY
    logger.debug(
        "models.dev refresh failed (%s); retry suppressed for %ds: %s",
        where,
        _MODELS_DEV_RETRY_DELAY,
        exc,
    )


def _background_refresh_models_dev() -> None:
    """Best-effort refresh after serving stale cache data."""
    global _models_dev_refresh_in_flight
    try:
        data = _fetch_models_dev_from_network()
        with _models_dev_fetch_lock:
            _commit_registry(data, where="background")
    except Exception as e:
        with _models_dev_fetch_lock:
            _note_refresh_failure(e, where="background")
    finally:
        with _models_dev_refresh_lock:
            _models_dev_refresh_in_flight = False


def _start_background_refresh_models_dev() -> None:
    """Start one daemon refresh worker if none is already running.

    Honors the process-wide failure backoff: after a failed refresh,
    no new background worker is spawned until _models_dev_retry_after.
    """
    global _models_dev_refresh_in_flight
    if time.time() < _models_dev_retry_after:
        return
    with _models_dev_refresh_lock:
        if _models_dev_refresh_in_flight:
            return
        _models_dev_refresh_in_flight = True
    thread = threading.Thread(
        target=_background_refresh_models_dev,
        name="models-dev-refresh",
        daemon=True,
    )
    try:
        thread.start()
    except Exception as e:
        with _models_dev_refresh_lock:
            _models_dev_refresh_in_flight = False
        logger.debug("Failed to start models.dev refresh thread: %s", e)


def fetch_models_dev(
    force_refresh: bool = False, *, allow_network: bool = True
) -> dict[str, Any]:
    """Fetch models.dev registry. Cache hierarchy: in-mem → disk → network.

    Returns the full registry dict keyed by provider ID, or empty dict on failure.

    Args:
        force_refresh: If True, bypass cache (used by `models refresh`).
        allow_network:  If False, never touch the network — for latency-sensitive
                       paths. Returns whatever cache exists.

    Cache hierarchy (when force_refresh=False):
      1. Fresh in-memory cache → return immediately.
      2. Stale in-memory cache → return immediately and refresh in a single
         background daemon thread. Callers never block on the network.
      3. Disk cache file (any age) → load, populate in-mem, return
         immediately. Stale disk caches trigger background refresh.
      4. No cache at all → singleflight foreground network fetch.
      5. Failed refresh (foreground or background) suppresses further
         refreshes for 5 minutes process-wide.
    """
    global _models_dev_cache, _models_dev_cache_time, _models_dev_retry_after

    if not allow_network:
        if _models_dev_cache:
            return _models_dev_cache
        disk_data = _load_disk_cache()
        if disk_data:
            _models_dev_cache = disk_data
            disk_age = _disk_cache_age_seconds()
            _models_dev_cache_time = time.time() - disk_age if disk_age is not None else 0.0
        return _models_dev_cache

    if force_refresh:
        try:
            data = _fetch_models_dev_from_network()
            with _models_dev_fetch_lock:
                _commit_registry(data, where="force_refresh")
            return data
        except Exception as e:
            logger.debug("models.dev force refresh failed: %s", e)
            # Fall back to cache (any age) instead of failing
            if _models_dev_cache:
                return _models_dev_cache
            disk_data = _load_disk_cache()
            if disk_data:
                _models_dev_cache = disk_data
                return disk_data
            return {}

    # 1. Fresh in-memory cache
    if _models_dev_cache and (time.time() - _models_dev_cache_time) < _MODELS_DEV_CACHE_TTL:
        return _models_dev_cache

    # 2. Stale in-memory cache → return + refresh in background
    if _models_dev_cache:
        _start_background_refresh_models_dev()
        return _models_dev_cache

    # 3. Disk cache
    disk_data = _load_disk_cache()
    if disk_data:
        _models_dev_cache = disk_data
        disk_age = _disk_cache_age_seconds()
        if disk_age is not None:
            _models_dev_cache_time = time.time() - disk_age
        else:
            _models_dev_cache_time = 0.0
        _start_background_refresh_models_dev()
        return _models_dev_cache

    # 4. No cache at all → singleflight foreground network fetch
    with _models_dev_fetch_lock:
        # Double-check: another thread may have populated while we waited
        if _models_dev_cache:
            return _models_dev_cache
        try:
            data = _fetch_models_dev_from_network()
            _commit_registry(data, where="foreground")
            return data
        except Exception as e:
            _note_refresh_failure(e, where="foreground")
            return {}


def _extract_limit(entry: dict[str, Any]) -> tuple[int, int]:
    """Return (context_window, max_output) from models.dev entry."""
    limit = entry.get("limit", {}) or {}
    context = limit.get("context", 0) or 0
    output = limit.get("output", 0) or 0
    return int(context), int(output)


def _extract_cost(entry: dict[str, Any]) -> tuple[float, float, float | None, float | None]:
    """Return (input, output, cache_read, cache_write) from models.dev entry."""
    cost = entry.get("cost", {}) or {}
    inp = cost.get("input", 0.0) or 0.0
    out = cost.get("output", 0.0) or 0.0
    cr = cost.get("cache_read")
    cw = cost.get("cache_write")
    return float(inp), float(out), (float(cr) if cr is not None else None), (
        float(cw) if cw is not None else None
    )


def _extract_modalities(entry: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (input_modalities, output_modalities) from models.dev entry."""
    modalities = entry.get("modalities", {}) or {}
    inputs = tuple(modalities.get("input", []) or ())
    outputs = tuple(modalities.get("output", []) or ())
    return inputs, outputs


def _parse_model_info(model_id: str, raw: dict[str, Any], provider_id: str) -> ModelInfo:
    """Parse a models.dev model entry into a ModelInfo dataclass."""
    context, max_output = _extract_limit(raw)
    cost_in, cost_out, cache_read, cache_write = _extract_cost(raw)
    inputs, outputs = _extract_modalities(raw)
    return ModelInfo(
        id=model_id,
        name=str(raw.get("name", model_id)),
        family=str(raw.get("family", "")),
        provider_id=provider_id,
        reasoning=bool(raw.get("reasoning", False)),
        tool_call=bool(raw.get("tool_call", False)),
        attachment=bool(raw.get("attachment", False)),
        temperature=bool(raw.get("temperature", False)),
        structured_output=bool(raw.get("structured_output", False)),
        open_weights=bool(raw.get("open_weights", False)),
        input_modalities=inputs,
        output_modalities=outputs,
        context_window=context,
        max_output=max_output,
        cost_input=cost_in,
        cost_output=cost_out,
        cost_cache_read=cache_read,
        cost_cache_write=cache_write,
        knowledge_cutoff=str(raw.get("knowledge", "")),
        release_date=str(raw.get("release_date", "")),
        status=str(raw.get("status", "")),
    )


def _parse_provider_info(provider_id: str, raw: dict[str, Any]) -> ProviderInfo:
    """Parse a models.dev provider entry into a ProviderInfo dataclass."""
    env_vars = tuple(raw.get("env", []) or [])
    models = raw.get("models", {}) or {}
    return ProviderInfo(
        id=provider_id,
        name=str(raw.get("name", provider_id)),
        env=env_vars,
        api=str(raw.get("api", "")),
        doc=str(raw.get("doc", "")),
        model_count=len(models),
    )


def get_provider_info(provider: str) -> ProviderInfo | None:
    """Fetch models.dev provider info for the given provider ID.

    Returns None if the provider is not in the registry.
    """
    registry = fetch_models_dev()
    raw = registry.get(provider)
    if not isinstance(raw, dict):
        return None
    return _parse_provider_info(provider, raw)


def get_model_info(provider: str, model: str) -> ModelInfo | None:
    """Fetch models.dev model info for the given provider/model pair.

    Returns None if the provider or model is not in the registry.
    """
    registry = fetch_models_dev()
    provider_data = registry.get(provider)
    if not isinstance(provider_data, dict):
        return None
    models = provider_data.get("models", {})
    if not isinstance(models, dict):
        return None
    raw = models.get(model)
    if not isinstance(raw, dict):
        return None
    return _parse_model_info(model, raw, provider)


def list_provider_models(provider: str) -> list[str]:
    """Return all model IDs known to models.dev for the given provider."""
    registry = fetch_models_dev()
    provider_data = registry.get(provider)
    if not isinstance(provider_data, dict):
        return []
    models = provider_data.get("models", {})
    if not isinstance(models, dict):
        return []
    return sorted(models.keys())


def list_agentic_models(provider: str) -> list[str]:
    """Return models with tool_calling capability for the given provider."""
    registry = fetch_models_dev()
    provider_data = registry.get(provider)
    if not isinstance(provider_data, dict):
        return []
    models = provider_data.get("models", {})
    if not isinstance(models, dict):
        return []
    return sorted(
        model_id
        for model_id, raw in models.items()
        if isinstance(raw, dict) and raw.get("tool_call", False)
    )


def get_max_output_tokens(provider: str, model: str) -> int:
    """Return the model's max_output from models.dev, or 0 if unknown.

    Used by Anthropic adapter to set max_tokens without hardcoding.
    """
    info = get_model_info(provider, model)
    if info is None:
        return 0
    return info.max_output


def get_context_window(provider: str, model: str) -> int:
    """Return the model's context_window from models.dev, or 0 if unknown."""
    info = get_model_info(provider, model)
    if info is None:
        return 0
    return info.context_window
