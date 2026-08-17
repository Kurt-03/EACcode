"""Tests for the model router: provider config, kwargs, and MiniMax-specific setup."""

from __future__ import annotations

from eaccode import router


class TestMinimaxSetup:
    """MiniMax-M3 needs an explicit base_url and max_tokens to work."""

    def test_minimax_default_max_tokens(self) -> None:
        """Without caller max_tokens, MiniMax gets 4096 by default."""
        conf = {"providers": {"minimax": {"api_key": "sk-fake"}}}
        kwargs = router._completion_kwargs(
            "minimax/MiniMax-M3",
            [{"role": "user", "content": "hi"}],
            conf, 30.0, None,
        )
        assert kwargs["max_tokens"] == 4096

    def test_minimax_base_url_propagation(self) -> None:
        """base_url from config is forwarded to LiteLLM as api_base."""
        conf = {"providers": {"minimax": {
            "api_key": "sk-fake",
            "base_url": "https://api.minimax.io/anthropic",
        }}}
        kwargs = router._completion_kwargs(
            "minimax/MiniMax-M3",
            [{"role": "user", "content": "hi"}],
            conf, 30.0, None,
        )
        assert kwargs["api_base"] == "https://api.minimax.io/anthropic"

    def test_minimax_explicit_max_tokens_not_overridden(self) -> None:
        """Caller-provided max_tokens is preserved."""
        conf = {"providers": {"minimax": {"api_key": "sk-fake"}}}
        kwargs = router._completion_kwargs(
            "minimax/MiniMax-M3",
            [{"role": "user", "content": "hi"}],
            conf, 30.0, {"max_tokens": 100},
        )
        assert kwargs["max_tokens"] == 100

    def test_non_minimax_unaffected(self) -> None:
        """Other providers do NOT get a default max_tokens."""
        conf = {"providers": {"anthropic": {"api_key": "sk-fake"}}}
        kwargs = router._completion_kwargs(
            "anthropic/claude-sonnet-4",
            [{"role": "user", "content": "hi"}],
            conf, 30.0, None,
        )
        assert "max_tokens" not in kwargs

    def test_known_models_includes_minimax_family(self) -> None:
        """All real MiniMax-M3 / M2.x models are in the catalog."""
        expected = [
            "minimax/MiniMax-M3",
            "minimax/MiniMax-M2.5",
            "minimax/MiniMax-M2.1",
            "minimax/MiniMax-M2.1-lightning",
        ]
        assert all(model in router.KNOWN_MODELS["minimax"] for model in expected)
