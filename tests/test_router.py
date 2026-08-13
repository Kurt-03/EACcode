"""Tests for the model router (Phase A3)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from eaccode import config as cfg
from eaccode import router


def _conf(**overrides: Any) -> dict[str, Any]:
    conf = cfg.defaults()
    conf.update(overrides)
    return conf


def _fake_response(text: str = "pong") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
    )


class TestApiKey:
    def test_env_wins_over_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "from-env")
        provider = {"api_key": "from-file", "api_key_env": "MY_KEY"}
        assert router.resolve_api_key(provider) == "from-env"

    def test_file_key_used_without_env(self) -> None:
        assert router.resolve_api_key({"api_key": "sk-file"}) == "sk-file"

    def test_no_key_returns_none(self) -> None:
        assert router.resolve_api_key({}) is None
        assert router.resolve_api_key(None) is None

    def test_env_var_set_but_empty_falls_back_to_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_KEY", "")
        assert router.resolve_api_key({"api_key": "sk-file", "api_key_env": "MY_KEY"}) == "sk-file"


class TestChain:
    def test_model_chain_default_and_fallback(self) -> None:
        conf = _conf(model={"default": "a/x", "fallback": ["b/y", "c/z"]})
        assert router.model_chain(conf) == ["a/x", "b/y", "c/z"]

    def test_model_chain_empty_without_default(self) -> None:
        assert router.model_chain(_conf(model={"default": "", "fallback": []})) == []

    def test_all_model_ids_combines_sources(self) -> None:
        conf = _conf(
            model={"default": "ollama/llama3.2", "fallback": []},
            providers={"ollama": {"models": ["ollama/custom-model"]}},
        )
        ids = router.all_model_ids(conf)
        assert "ollama/llama3.2" in ids
        assert "ollama/custom-model" in ids
        assert "ollama/llama3.2" in ids  # known catalog entry
        assert ids.count("ollama/llama3.2") == 1  # deduplicated


class TestCalls:
    def test_completion_text_passes_key_and_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}
        import litellm

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            captured.update(kwargs)
            return _fake_response()

        monkeypatch.setattr(litellm, "completion", fake_completion)
        conf = _conf(
            providers={
                "openrouter": {
                    "api_key": "sk-test",
                    "base_url": "https://example.test/v1",
                }
            }
        )
        text = router.completion_text(
            "openrouter/foo", [{"role": "user", "content": "hi"}], conf
        )
        assert text == "pong"
        assert captured["model"] == "openrouter/foo"
        assert captured["api_key"] == "sk-test"
        assert captured["api_base"] == "https://example.test/v1"

    def test_completion_error_becomes_model_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import litellm

        def boom(**kwargs: Any) -> None:
            raise RuntimeError("connection refused")

        monkeypatch.setattr(litellm, "completion", boom)
        with pytest.raises(router.ModelError, match="connection refused"):
            router.completion_text("x/y", [], _conf())

    def test_call_model_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            calls.append(kwargs["model"])
            return _fake_response()

        import litellm

        monkeypatch.setattr(litellm, "completion", fake_completion)
        conf = _conf(model={"default": "openrouter/a", "fallback": ["openrouter/b"]})
        text = router.call_model(conf, [{"role": "user", "content": "hi"}])
        assert text == "pong"
        assert calls == ["openrouter/a"]

    def test_call_model_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def flaky_completion(**kwargs: Any) -> SimpleNamespace:
            calls.append(kwargs["model"])
            if kwargs["model"] == "openrouter/a":
                raise RuntimeError("rate limited")
            return _fake_response()

        import litellm

        monkeypatch.setattr(litellm, "completion", flaky_completion)
        conf = _conf(model={"default": "openrouter/a", "fallback": ["openrouter/b"]})
        assert router.call_model(conf, []) == "pong"
        assert calls == ["openrouter/a", "openrouter/b"]

    def test_call_model_all_fail_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        def boom(**kwargs: Any) -> None:
            raise RuntimeError("down")

        monkeypatch.setattr(litellm, "completion", boom)
        conf = _conf(model={"default": "a/x", "fallback": ["b/y"]})
        with pytest.raises(router.ModelError, match="all models failed"):
            router.call_model(conf, [])

    def test_call_model_without_default_raises(self) -> None:
        with pytest.raises(router.ModelError, match="model set-default"):
            router.call_model(_conf(model={"default": "", "fallback": []}), [])

    def test_call_model_explicit_id_skips_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            calls.append(kwargs["model"])
            return _fake_response()

        import litellm

        monkeypatch.setattr(litellm, "completion", fake_completion)
        conf = _conf(model={"default": "a/x", "fallback": []})
        router.call_model(conf, [], model_id="b/y")
        assert calls == ["b/y"]

    def test_ping_returns_reply(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import litellm

        def fake_completion(**kwargs: Any) -> SimpleNamespace:
            assert kwargs["messages"][0]["content"] == router.PING_PROMPT
            return _fake_response("pong")

        monkeypatch.setattr(litellm, "completion", fake_completion)
        assert router.ping_model("x/y", _conf()) == "pong"
