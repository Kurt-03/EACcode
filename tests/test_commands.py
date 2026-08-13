"""Tests for the config subcommands (CLI + REPL shared layer, Phase A2/A3)."""

from __future__ import annotations

import getpass
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from eaccode import config as cfg
from eaccode import skills
from eaccode.commands import (
    run_config_command,
    run_memory_command,
    run_model_command,
    run_provider_command,
    run_session_command,
    run_skill_command,
)


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[callable, Path]:
    """Point the config at a temp path; return (run_fn, config_path)."""
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(cfg, "config_path", lambda: target)
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)

    def run(*args: str) -> tuple[int, str]:
        stdout = io.StringIO()
        code = run_config_command(list(args), stdout=stdout)
        return code, stdout.getvalue()

    return run, target


@pytest.fixture
def provider_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[callable, Path]:
    """Point the config at a temp path; return (provider_run_fn, config_path)."""
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(cfg, "config_path", lambda: target)
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    run_config_command(["init"], stdout=io.StringIO())

    def run(*args: str) -> tuple[int, str]:
        stdout = io.StringIO()
        code = run_provider_command(list(args), stdout=stdout)
        return code, stdout.getvalue()

    return run, target


@pytest.fixture
def model_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[callable, Path]:
    """Point the config at a temp path; return (model_run_fn, config_path)."""
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(cfg, "config_path", lambda: target)
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    run_config_command(["init"], stdout=io.StringIO())

    def run(*args: str) -> tuple[int, str]:
        stdout = io.StringIO()
        code = run_model_command(list(args), stdout=stdout)
        return code, stdout.getvalue()

    return run, target


def test_usage_without_args(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    code, out = run()
    assert code == 0
    assert "Usage: config" in out


def test_init_creates_config(runner: tuple[callable, Path]) -> None:
    run, target = runner
    code, out = run("init")
    assert code == 0
    assert "created" in out
    assert str(target) in out
    assert target.exists()


def test_init_twice_is_idempotent(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    code, out = run("init")
    assert code == 0
    assert "already exists" in out


def test_path_prints_config_path(runner: tuple[callable, Path]) -> None:
    run, target = runner
    code, out = run("path")
    assert code == 0
    assert out.strip() == str(target)


def test_show_without_config_errors(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    code, out = run("show")
    assert code == 1
    assert "config init" in out


def test_show_masks_secrets(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    run("set", "providers.openrouter.api_key", "sk-super-secret-value")
    code, out = run("show")
    assert code == 0
    assert "sk-***" in out
    assert "sk-super-secret-value" not in out
    assert "api_key: set (file)" in out


def test_show_reports_env_key_status(
    runner: tuple[callable, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _ = runner
    run("init")
    run("set", "providers.openrouter.api_key_env", "OPENROUTER_API_KEY")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env-value")
    _, out = run("show")
    assert "set (env: OPENROUTER_API_KEY)" in out
    assert "sk-env-value" not in out


def test_set_and_get_roundtrip(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    code, _ = run("set", "model.default", "openrouter/foo")
    assert code == 0
    code, out = run("get", "model.default")
    assert code == 0
    assert out.strip() == "openrouter/foo"


def test_set_list_value(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    run("set", "model.fallback", "a, b")
    code, out = run("get", "model.fallback")
    assert code == 0
    assert out.strip() == "[a, b]"


def test_get_unknown_key_errors(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    code, out = run("get", "model.nope")
    assert code == 1
    assert "unknown config key" in out


def test_get_refuses_secret(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    run("set", "providers.openrouter.api_key", "sk-x")
    code, out = run("get", "providers.openrouter.api_key")
    assert code == 1
    assert "refusing" in out


def test_set_unknown_key_errors(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    code, out = run("set", "model.nope", "x")
    assert code == 1
    assert "unknown config key" in out


def test_set_key_stores_hidden(
    runner: tuple[callable, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    run, target = runner
    run("init")
    monkeypatch.setattr(getpass, "getpass", lambda prompt="", stream=None: "sk-hidden-123")
    code, out = run("set-key", "providers.openrouter.api_key")
    assert code == 0
    assert "secret stored" in out
    assert "sk-hidden-123" in target.read_text(encoding="utf-8")
    _, shown = run("show")
    assert "sk-hidden-123" not in shown
    assert "sk-***" in shown


def test_set_key_refuses_non_secret(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    code, out = run("set-key", "model.default")
    assert code == 1
    assert "does not look like a secret" in out


def test_set_key_empty_secret_errors(
    runner: tuple[callable, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _ = runner
    run("init")
    monkeypatch.setattr(getpass, "getpass", lambda prompt="", stream=None: "")
    code, out = run("set-key", "providers.openrouter.api_key")
    assert code == 1
    assert "empty secret" in out


def test_unset_removes_value(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    run("init")
    run("set", "model.default", "x")
    code, out = run("unset", "model.default")
    assert code == 0
    assert out.strip() == "ok"
    code, out = run("get", "model.default")
    assert code == 0
    assert out.strip() == "(unset)"


def test_unknown_subcommand_errors(runner: tuple[callable, Path]) -> None:
    run, _ = runner
    code, out = run("frobnicate")
    assert code == 1
    assert "Unknown config command" in out


def test_bad_yaml_shows_clear_error(runner: tuple[callable, Path]) -> None:
    run, target = runner
    target.write_text("model: [broken\n", encoding="utf-8")
    code, out = run("show")
    assert code == 1
    assert "invalid YAML" in out


class TestProviderCommands:
    def test_add_with_env_and_base_url(self, provider_runner: tuple[callable, Path]) -> None:
        run, target = provider_runner
        code, out = run("add", "openrouter", "--api-key-env", "OPENROUTER_API_KEY")
        assert code == 0
        assert "added" in out
        conf = cfg.load_config()
        assert conf["providers"]["openrouter"]["api_key_env"] == "OPENROUTER_API_KEY"

    def test_add_without_name_usage(self, provider_runner: tuple[callable, Path]) -> None:
        run, _ = provider_runner
        code, out = run("add")
        assert code == 1
        assert "Usage" in out

    def test_add_bad_flag(self, provider_runner: tuple[callable, Path]) -> None:
        run, _ = provider_runner
        code, out = run("add", "foo", "--nonsense", "x")
        assert code == 1
        assert "unknown flag" in out

    def test_list_shows_providers(self, provider_runner: tuple[callable, Path]) -> None:
        run, _ = provider_runner
        run("add", "ollama", "--base-url", "http://localhost:11434")
        run("add", "openrouter", "--api-key-env", "OPENROUTER_API_KEY")
        code, out = run("list")
        assert code == 0
        assert "ollama" in out
        assert "openrouter" in out
        assert "http://localhost:11434" in out

    def test_list_empty_hint(self, provider_runner: tuple[callable, Path]) -> None:
        run, _ = provider_runner
        code, out = run("list")
        assert code == 0
        assert "provider add" in out

    def test_remove(self, provider_runner: tuple[callable, Path]) -> None:
        run, _ = provider_runner
        run("add", "ollama")
        code, out = run("remove", "ollama")
        assert code == 0
        assert "removed" in out
        assert "ollama" not in cfg.load_config()["providers"]

    def test_remove_unknown_errors(self, provider_runner: tuple[callable, Path]) -> None:
        run, _ = provider_runner
        code, out = run("remove", "ghost")
        assert code == 1
        assert "unknown provider" in out

    def test_set_key_uses_config_path(
        self, provider_runner: tuple[callable, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run, target = provider_runner
        run("add", "openrouter")
        monkeypatch.setattr(getpass, "getpass", lambda prompt="", stream=None: "sk-xyz-123")
        code, out = run("set-key", "openrouter")
        assert code == 0
        assert "secret stored" in out
        assert "sk-xyz-123" in target.read_text(encoding="utf-8")


class TestModelCommands:
    def test_set_default_and_list(self, model_runner: tuple[callable, Path]) -> None:
        run, _ = model_runner
        code, out = run("set-default", "openrouter/anthropic/claude-sonnet-4")
        assert code == 0
        assert "default model" in out
        code, out = run("list")
        assert code == 0
        assert "default:" in out
        assert "openrouter/anthropic/claude-sonnet-4" in out
        assert "(default)" in out

    def test_set_fallback_chain(self, model_runner: tuple[callable, Path]) -> None:
        run, _ = model_runner
        code, out = run("set-fallback", "ollama/llama3.2, ollama/qwen2.5")
        assert code == 0
        assert "[ollama/llama3.2, ollama/qwen2.5]" in out

    def test_add_custom_model(self, model_runner: tuple[callable, Path]) -> None:
        run, _ = model_runner
        code, out = run("add", "ollama/deepseek-r1", "--base-url", "http://localhost:11434")
        assert code == 0
        assert "registered" in out
        conf = cfg.load_config()
        assert "ollama/deepseek-r1" in conf["providers"]["ollama"]["models"]
        assert conf["providers"]["ollama"]["base_url"] == "http://localhost:11434"

    def test_add_rejects_bad_id(self, model_runner: tuple[callable, Path]) -> None:
        run, _ = model_runner
        code, out = run("add", "no-slash")
        assert code == 1
        assert "<provider>/<model>" in out

    def test_ping_success(
        self, model_runner: tuple[callable, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run, _ = model_runner
        import litellm

        def fake_completion(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="pong"))]
            )

        monkeypatch.setattr(litellm, "completion", fake_completion)
        code, out = run("ping", "openrouter/foo")
        assert code == 0
        assert "replied: pong" in out

    def test_ping_failure_clean_error(
        self, model_runner: tuple[callable, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run, _ = model_runner
        import litellm

        def boom(**kwargs: object) -> None:
            raise RuntimeError("invalid api key")

        monkeypatch.setattr(litellm, "completion", boom)
        code, out = run("ping", "openrouter/foo")
        assert code == 1
        assert "Error" in out
        assert "invalid api key" in out

    def test_ping_usage(self, model_runner: tuple[callable, Path]) -> None:
        run, _ = model_runner
        code, out = run("ping")
        assert code == 1
        assert "Usage" in out

    def test_unknown_model_command(self, model_runner: tuple[callable, Path]) -> None:
        run, _ = model_runner
        code, out = run("frobnicate")
        assert code == 1
        assert "Unknown model command" in out


class TestMemoryCommands:
    @pytest.fixture
    def memory_runner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> callable:
        monkeypatch.setattr(cfg, "config_path", lambda: tmp_path / "config.yaml")
        monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        run_config_command(["init"], stdout=io.StringIO())

        def run(*args: str) -> tuple[int, str]:
            stdout = io.StringIO()
            code = run_memory_command(list(args), stdout=stdout)
            return code, stdout.getvalue()

        return run

    def test_add_and_show(self, memory_runner: callable) -> None:
        run = memory_runner
        code, out = run("add", "Agent", "fakt")
        assert code == 0
        assert out.strip() == "ok"
        code, out = run("show")
        assert code == 0
        assert "- Agent fakt" in out

    def test_user_add(self, memory_runner: callable) -> None:
        run = memory_runner
        code, out = run("user", "add", "spricht", "Deutsch")
        assert code == 0
        code, out = run("show")
        assert "- spricht Deutsch" in out

    def test_remove(self, memory_runner: callable) -> None:
        run = memory_runner
        run("add", "alter Fakt")
        run("add", "neuer Fakt")
        code, out = run("remove", "alter")
        assert code == 0
        code, out = run("show")
        assert "alter Fakt" not in out
        assert "- neuer Fakt" in out

    def test_usage_without_args(self, memory_runner: callable) -> None:
        run = memory_runner
        code, out = run()
        assert code == 0
        assert "Usage: memory" in out

    def test_unknown_command(self, memory_runner: callable) -> None:
        run = memory_runner
        code, out = run("frobnicate")
        assert code == 1
        assert "Unknown memory command" in out


class TestSkillCommands:
    @pytest.fixture
    def skill_runner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> callable:
        monkeypatch.setattr(cfg, "config_path", lambda: tmp_path / "config.yaml")
        monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        run_config_command(["init"], stdout=io.StringIO())

        def run(*args: str) -> tuple[int, str]:
            stdout = io.StringIO()
            code = run_skill_command(list(args), stdout=stdout)
            return code, stdout.getvalue()

        return run

    def test_new_and_list(self, skill_runner: callable) -> None:
        run = skill_runner
        code, out = run(
            "new", "zeit-helfer", "--trigger", "uhrzeit", "--description", "Zeit anzeigen"
        )
        assert code == 0
        assert "created" in out
        code, out = run("list")
        assert code == 0
        assert "zeit-helfer" in out
        assert "uhrzeit" in out

    def test_new_requires_trigger(self, skill_runner: callable) -> None:
        run = skill_runner
        code, out = run("new", "x")
        assert code == 1
        assert "--trigger is required" in out

    def test_view_shows_content(self, skill_runner: callable) -> None:
        run = skill_runner
        run("new", "abc", "--trigger", "abc")
        code, out = run("view", "abc")
        assert code == 0
        assert "name: abc" in out

    def test_view_missing_errors(self, skill_runner: callable) -> None:
        run = skill_runner
        code, out = run("view", "ghost")
        assert code == 1
        assert "does not exist" in out

    def test_remove(self, skill_runner: callable) -> None:
        run = skill_runner
        run("new", "abc", "--trigger", "abc")
        code, out = run("remove", "abc")
        assert code == 0
        assert "removed" in out
        assert skills.list_skills() == []

    def test_usage_without_args(self, skill_runner: callable) -> None:
        run = skill_runner
        code, out = run()
        assert code == 0
        assert "Usage: skill" in out

    def test_unknown_command(self, skill_runner: callable) -> None:
        run = skill_runner
        code, out = run("frobnicate")
        assert code == 1
        assert "Unknown skill command" in out


class TestSessionCommands:
    @pytest.fixture
    def session_runner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> callable:
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        run_config_command(["init"], stdout=io.StringIO())

        def run(*args: str) -> tuple[int, str]:
            stdout = io.StringIO()
            code = run_session_command(list(args), stdout=stdout)
            return code, stdout.getvalue()

        return run

    def test_browse_empty(self, session_runner: callable) -> None:
        run = session_runner
        code, out = run("browse")
        assert code == 0
        assert "no sessions yet" in out

    def test_browse_lists_sessions(self, session_runner: callable) -> None:
        run = session_runner
        from eaccode import store

        session_id = store.new_session(title="Mein Titel")
        store.add_message(session_id, "user", "hallo")
        code, out = run("browse")
        assert code == 0
        assert session_id in out
        assert "Mein Titel" in out

    def test_search_finds_content(self, session_runner: callable) -> None:
        run = session_runner
        from eaccode import store

        session_id = store.new_session(title="Router")
        store.add_message(session_id, "user", "Wie baue ich LiteLLM ein?")
        code, out = run("search", "LiteLLM")
        assert code == 0
        assert session_id in out

    def test_search_no_hits(self, session_runner: callable) -> None:
        run = session_runner
        code, out = run("search", "gibtsnicht")
        assert code == 0
        assert "no sessions match" in out

    def test_show_session(self, session_runner: callable) -> None:
        run = session_runner
        from eaccode import store

        session_id = store.new_session()
        store.add_message(session_id, "user", "frage")
        store.add_message(session_id, "assistant", "antwort")
        code, out = run("show", session_id)
        assert code == 0
        assert "[user] frage" in out
        assert "[assistant] antwort" in out

    def test_show_unknown_errors(self, session_runner: callable) -> None:
        run = session_runner
        code, out = run("show", "ghost")
        assert code == 1
        assert "no session" in out

    def test_usage_without_args(self, session_runner: callable) -> None:
        run = session_runner
        code, out = run()
        assert code == 0
        assert "Usage: session" in out
