"""Tests for the config storage layer (Phase A2)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from eaccode import config as cfg


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the config at a temp location and return its path."""
    target = tmp_path / "config.yaml"
    monkeypatch.setattr(cfg, "config_path", lambda: target)
    monkeypatch.setattr(cfg, "config_dir", lambda: tmp_path)
    return target


class TestDirectories:
    @pytest.mark.skipif(os.name != "nt", reason="Windows path behavior")
    def test_config_dir_windows_uses_localappdata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\test\\AppData\\Local")
        assert cfg.config_dir() == Path("C:\\Users\\test\\AppData\\Local\\eaccode")

    @pytest.mark.skipif(os.name == "nt", reason="POSIX path behavior (runs in CI on Linux)")
    def test_config_dir_unix_uses_xdg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        base = Path("/tmp/eac-test-base")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(base))
        assert cfg.config_dir() == base / "eaccode"

    @pytest.mark.skipif(os.name == "nt", reason="POSIX path behavior (runs in CI on Linux)")
    def test_config_dir_unix_falls_back_to_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/tmp/eac-test-home")))
        assert cfg.config_dir() == Path("/tmp/eac-test-home/.config/eaccode")

    @pytest.mark.skipif(os.name != "nt", reason="Windows path behavior")
    def test_data_dir_windows_matches_config_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOCALAPPDATA", "C:\\Users\\test\\AppData\\Local")
        assert cfg.data_dir() == cfg.config_dir()


class TestDefaultsAndMerge:
    def test_defaults_have_expected_structure(self) -> None:
        d = cfg.defaults()
        assert d["model"]["default"] == ""
        assert d["model"]["fallback"] == []
        assert d["providers"] == {}
        assert d["paths"]["data"]

    def test_load_merges_over_defaults(self, tmp_config: Path) -> None:
        tmp_config.write_text("model:\n  default: openrouter/foo\n", encoding="utf-8")
        conf = cfg.load_config()
        assert conf["model"]["default"] == "openrouter/foo"
        assert conf["model"]["fallback"] == []
        assert "data" in conf["paths"]

    def test_load_missing_raises(self, tmp_config: Path) -> None:
        with pytest.raises(cfg.ConfigError, match="config init"):
            cfg.load_config()

    def test_load_invalid_yaml_raises(self, tmp_config: Path) -> None:
        tmp_config.write_text("model: [unclosed\n", encoding="utf-8")
        with pytest.raises(cfg.ConfigError, match="invalid YAML"):
            cfg.load_config()

    def test_load_non_mapping_raises(self, tmp_config: Path) -> None:
        tmp_config.write_text("- just\n- a\n- list\n", encoding="utf-8")
        with pytest.raises(cfg.ConfigError, match="mapping"):
            cfg.load_config()

    def test_save_and_load_roundtrip(self, tmp_config: Path) -> None:
        conf = cfg.defaults()
        conf["model"]["default"] = "anthropic/claude-sonnet-4"
        cfg.save_config(conf, tmp_config)
        assert cfg.load_config()["model"]["default"] == "anthropic/claude-sonnet-4"

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "dir" / "config.yaml"
        cfg.save_config(cfg.defaults(), target)
        assert target.exists()

    @pytest.mark.skipif(os.name == "nt", reason="chmod semantics are POSIX-only")
    def test_save_restricts_permissions(
        self, tmp_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(os, "name", "posix")
        cfg.save_config(cfg.defaults(), tmp_config)
        assert tmp_config.stat().st_mode & 0o777 == 0o600


class TestMasking:
    def test_mask_long_secret_keeps_prefix(self) -> None:
        assert cfg.mask_secret("sk-abcdef123456") == "sk-***"

    def test_mask_short_secret_fully(self) -> None:
        assert cfg.mask_secret("abc") == "***"

    def test_mask_empty_or_non_string(self) -> None:
        assert cfg.mask_secret("") == "***"
        assert cfg.mask_secret(None) == "***"
        assert cfg.mask_secret(42) == "***"

    def test_is_secret_key_detects_api_keys(self) -> None:
        assert cfg.is_secret_key("providers.openrouter.api_key")
        assert cfg.is_secret_key("providers.foo.api_key_env") is False
        assert cfg.is_secret_key("model.default") is False


class TestKeyAccess:
    def test_get_value_nested(self) -> None:
        conf = {"model": {"default": "x"}}
        assert cfg.get_value(conf, "model.default") == "x"

    def test_get_value_unknown_raises(self) -> None:
        with pytest.raises(cfg.ConfigError, match="unknown config key"):
            cfg.get_value({"model": {}}, "model.nope")

    def test_set_value_unknown_raises(self) -> None:
        with pytest.raises(cfg.ConfigError, match="unknown config key"):
            cfg.set_value({"model": {}}, "model.nope", "x")

    def test_set_value_unknown_section_raises(self) -> None:
        with pytest.raises(cfg.ConfigError, match="unknown config section"):
            cfg.set_value({"model": {}}, "nope.x", "y")

    def test_set_value_coerces_list(self) -> None:
        conf = cfg.defaults()
        cfg.set_value(conf, "model.fallback", "a, b, c")
        assert conf["model"]["fallback"] == ["a", "b", "c"]

    def test_set_value_keeps_string(self) -> None:
        conf = cfg.defaults()
        cfg.set_value(conf, "model.default", "openrouter/x")
        assert conf["model"]["default"] == "openrouter/x"

    def test_delete_value(self) -> None:
        conf = {"model": {"default": "x"}}
        cfg.delete_value(conf, "model.default")
        assert "default" not in conf["model"]

    def test_delete_unknown_raises(self) -> None:
        with pytest.raises(cfg.ConfigError, match="unknown config key"):
            cfg.delete_value({"model": {}}, "model.nope")


class TestEnv:
    def test_load_env_from_config_dir(
        self, tmp_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_config.parent / ".env").write_text("EACCODE_TEST_VAR=from-env\n", encoding="utf-8")
        cfg.load_env()
        assert os.environ.get("EACCODE_TEST_VAR") == "from-env"
        monkeypatch.delenv("EACCODE_TEST_VAR", raising=False)

    def test_provider_key_status_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_API_KEY", "sk-xyz")
        assert cfg.provider_key_status({"api_key_env": "MY_API_KEY"}) == "set (env: MY_API_KEY)"

    def test_provider_key_status_file(self) -> None:
        assert cfg.provider_key_status({"api_key": "sk-xyz"}) == "set (file)"

    def test_provider_key_status_missing(self) -> None:
        assert cfg.provider_key_status({}) == "not set"
        assert cfg.provider_key_status(None) == "not set"


class TestYamlSerialization:
    def test_ensure_config_creates_defaults(self, tmp_config: Path) -> None:
        cfg.ensure_config()
        assert tmp_config.exists()
        raw = yaml.safe_load(tmp_config.read_text(encoding="utf-8"))
        assert raw["model"]["default"] == ""

    def test_ensure_config_is_idempotent(self, tmp_config: Path) -> None:
        cfg.ensure_config()
        cfg.ensure_config()
        assert tmp_config.exists()
