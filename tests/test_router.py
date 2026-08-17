"""Tests for the eaccode.router deprecation shim.

The router module is back-compat: it keeps working helpers (model_chain,
provider_names, all_model_ids, ModelError) and rejects removed LiteLLM
helpers with a clear error pointing to the new provider registry.
"""

from __future__ import annotations

import pytest

from eaccode import router


class TestKnownModels:
    def test_minimax_family_listed(self) -> None:
        for model in (
            "minimax/MiniMax-M3",
            "minimax/MiniMax-M2.5",
            "minimax/MiniMax-M2.1",
            "minimax/MiniMax-M2.1-lightning",
        ):
            assert model in router.KNOWN_MODELS["minimax"]

    def test_anthropic_models_listed(self) -> None:
        assert "anthropic/claude-sonnet-4" in router.KNOWN_MODELS["anthropic"]
        assert "anthropic/claude-opus-4" in router.KNOWN_MODELS["anthropic"]

    def test_known_models_returns_lists(self) -> None:
        for value in router.KNOWN_MODELS.values():
            assert isinstance(value, list)
            for item in value:
                assert isinstance(item, str)


class TestModelChain:
    def test_default_only(self) -> None:
        assert router.model_chain({"model": {"default": "anthropic/foo"}}) == [
            "anthropic/foo"
        ]

    def test_default_with_fallback(self) -> None:
        assert router.model_chain(
            {"model": {"default": "anthropic/foo", "fallback": ["anthropic/bar"]}}
        ) == ["anthropic/foo", "anthropic/bar"]

    def test_no_model_returns_empty(self) -> None:
        assert router.model_chain({}) == []
        assert router.model_chain({"model": {}}) == []


class TestAllModelIds:
    def test_chain_and_catalog(self) -> None:
        conf = {
            "model": {"default": "anthropic/foo", "fallback": []},
            "providers": {
                "anthropic": {
                    "models": ["anthropic/custom-model"],
                },
            },
        }
        ids = router.all_model_ids(conf)
        assert "anthropic/foo" in ids
        assert "anthropic/custom-model" in ids
        assert "anthropic/claude-sonnet-4" in ids
        # Deduplicated
        assert len(ids) == len(set(ids))

    def test_empty_config(self) -> None:
        assert router.all_model_ids({}) == []


class TestRemovedHelpers:
    """The removed LiteLLM helpers should raise a clear ModelError."""

    @pytest.mark.parametrize(
        "func",
        [
            router.completion_response,
            router.stream_completion,
            router.completion_text,
            router.call_model,
            router.ping_model,
        ],
    )
    def test_removed_helper_raises(self, func: object) -> None:
        with pytest.raises(router.ModelError, match="removed"):
            func()  # type: ignore[operator]
