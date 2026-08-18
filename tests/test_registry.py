"""Tests for tool registry (Phase G.1, Plan G v5)."""

from __future__ import annotations

import pytest

from eaccode import registry as reg
from eaccode.registry import REGISTRY, ToolEntry


@pytest.fixture(autouse=True)
def _reset():
    """Reset the global registry between tests."""
    for name in list(REGISTRY._tools.keys()):
        REGISTRY.deregister(name)
    yield
    for name in list(REGISTRY._tools.keys()):
        REGISTRY.deregister(name)


def _entry(name: str, toolset: str = "core", **kw) -> ToolEntry:
    return ToolEntry(
        name=name,
        toolset=toolset,
        schema={"name": name, "description": f"Description for {name}"},
        handler=lambda: f"result-{name}",
        description=f"Description for {name}",
        **kw,
    )


class TestRegister:
    def test_register_basic(self) -> None:
        REGISTRY.register(_entry("foo"))
        assert REGISTRY.get_entry("foo") is not None

    def test_register_rejects_duplicate_without_override(self) -> None:
        REGISTRY.register(_entry("foo", toolset="core"))
        REGISTRY.register(_entry("foo", toolset="plugin"))
        # second registration was rejected because override=False
        assert REGISTRY.get_entry("foo").toolset == "core"

    def test_register_with_override_replaces(self) -> None:
        REGISTRY.register(_entry("foo", toolset="core"))
        REGISTRY.register(_entry("foo", toolset="plugin", override=True))
        assert REGISTRY.get_entry("foo").toolset == "plugin"

    def test_deregister(self) -> None:
        REGISTRY.register(_entry("foo"))
        REGISTRY.deregister("foo")
        assert REGISTRY.get_entry("foo") is None

    def test_deregister_missing_is_silent(self) -> None:
        REGISTRY.deregister("nope")  # no error


class TestGetEntries:
    def test_get_names_for_toolset(self) -> None:
        REGISTRY.register(_entry("a", toolset="core"))
        REGISTRY.register(_entry("b", toolset="plugin"))
        REGISTRY.register(_entry("c", toolset="plugin"))
        assert REGISTRY.get_tool_names_for_toolset("core") == ["a"]
        assert REGISTRY.get_tool_names_for_toolset("plugin") == ["b", "c"]

    def test_get_registered_toolset_names(self) -> None:
        REGISTRY.register(_entry("a", toolset="core"))
        REGISTRY.register(_entry("b", toolset="plugin"))
        assert REGISTRY.get_registered_toolset_names() == ["core", "plugin"]


class TestGetDefinitions:
    def test_returns_openai_format(self) -> None:
        REGISTRY.register(_entry("foo"))
        defs = REGISTRY.get_definitions({"foo"})
        assert len(defs) == 1
        assert defs[0]["type"] == "function"
        assert defs[0]["function"]["name"] == "foo"
        assert defs[0]["function"]["description"] == "Description for foo"

    def test_skips_unavailable_via_check_fn(self) -> None:
        REGISTRY.register(_entry("foo", check_fn=lambda: False))
        defs = REGISTRY.get_definitions({"foo"}, quiet=True)
        assert defs == []

    def test_check_fn_exception_skips_tool(self) -> None:
        def bad():
            raise RuntimeError("boom")

        REGISTRY.register(_entry("foo", check_fn=bad))
        defs = REGISTRY.get_definitions({"foo"}, quiet=True)
        assert defs == []

    def test_dynamic_schema_overrides_applied(self) -> None:
        REGISTRY.register(
            _entry("foo", dynamic_schema_overrides=lambda: {"x-new": "y"})
        )
        defs = REGISTRY.get_definitions({"foo"})
        assert defs[0]["function"].get("x-new") == "y"

    def test_dynamic_overrides_exception_drops_overrides(self) -> None:
        REGISTRY.register(
            _entry("foo", dynamic_schema_overrides=lambda: 1 / 0)
        )
        defs = REGISTRY.get_definitions({"foo"})
        # Original schema still there
        assert defs[0]["function"]["name"] == "foo"

    def test_max_result_size_in_metadata(self) -> None:
        REGISTRY.register(_entry("foo", max_result_size_chars=4096))
        defs = REGISTRY.get_definitions({"foo"})
        meta = defs[0]["function"].get("metadata") or {}
        assert meta.get("max_result_size_chars") == 4096


class TestGeneration:
    def test_increments_on_register(self) -> None:
        gen0 = REGISTRY.generation
        REGISTRY.register(_entry("foo"))
        assert REGISTRY.generation > gen0

    def test_increments_on_deregister(self) -> None:
        REGISTRY.register(_entry("foo"))
        gen1 = REGISTRY.generation
        REGISTRY.deregister("foo")
        assert REGISTRY.generation > gen1


class TestModuleLevelHelpers:
    def test_module_register(self) -> None:
        reg.register(_entry("bar"))
        assert reg.get_entry("bar") is not None

    def test_module_get_definitions(self) -> None:
        reg.register(_entry("bar"))
        defs = reg.get_definitions({"bar"})
        assert len(defs) == 1
