"""Tests for tool_search (Phase G.2, Plan G v5)."""

from __future__ import annotations

import pytest

from eaccode import tool_search as ts


def _make_tool(name: str, description: str = "") -> dict:
    return {
        "type": "function",
        "function": {"name": name, "description": description},
    }


class TestIsDeferrable:
    def test_core_tool_not_deferrable(self) -> None:
        assert ts.is_deferrable_tool_name("read_file") is False
        assert ts.is_deferrable_tool_name("write_file") is False
        assert ts.is_deferrable_tool_name("run_command") is False

    def test_unknown_tool_is_deferrable(self) -> None:
        assert ts.is_deferrable_tool_name("mcp__server__tool") is True
        assert ts.is_deferrable_tool_name("custom_plugin_xyz") is True


class TestClassifyTools:
    def test_split(self) -> None:
        tools = [
            _make_tool("read_file"),
            _make_tool("write_file"),
            _make_tool("custom_thing"),
            _make_tool("mcp__foo__bar"),
        ]
        visible, deferrable = ts.classify_tools(tools)
        visible_names = {t["function"]["name"] for t in visible}
        deferrable_names = {t["function"]["name"] for t in deferrable}
        assert visible_names == {"read_file", "write_file"}
        assert deferrable_names == {"custom_thing", "mcp__foo__bar"}

    def test_empty(self) -> None:
        visible, deferrable = ts.classify_tools([])
        assert visible == []
        assert deferrable == []

    def test_no_function_key_goes_visible(self) -> None:
        tools = [{"type": "function"}]
        visible, deferrable = ts.classify_tools(tools)
        assert len(visible) == 1
        assert len(deferrable) == 0


class TestEstimateTokens:
    def test_empty(self) -> None:
        assert ts.estimate_tokens_from_schemas([]) == 0

    def test_one_tool(self) -> None:
        tools = [_make_tool("x", "hello world")]
        tokens = ts.estimate_tokens_from_schemas(tools)
        assert tokens > 0


class TestShouldActivate:
    def test_off_never(self) -> None:
        config = ts.ToolSearchConfig(enabled="off")
        assert ts.should_activate(config, deferrable_tokens=1000) is False

    def test_auto_with_deferrable(self) -> None:
        config = ts.ToolSearchConfig(enabled="auto")
        assert ts.should_activate(config, deferrable_tokens=1000) is True

    def test_auto_without_deferrable(self) -> None:
        config = ts.ToolSearchConfig(enabled="auto")
        assert ts.should_activate(config, deferrable_tokens=0) is False

    def test_on_with_deferrable(self) -> None:
        config = ts.ToolSearchConfig(enabled="on")
        assert ts.should_activate(config, deferrable_tokens=100) is True


class TestListingBudget:
    def test_zero_context_default(self) -> None:
        config = ts.ToolSearchConfig()
        assert ts.listing_token_budget(config, None, 500) == 2000

    def test_uses_pct(self) -> None:
        config = ts.ToolSearchConfig(catalog_budget_pct=0.05)
        assert ts.listing_token_budget(config, 100_000, 500) == 5000


class TestCatalog:
    def test_build(self) -> None:
        tools = [
            _make_tool("read_file", "Read a file"),
            _make_tool("custom_thing", "Does custom things"),
        ]
        catalog = ts.build_catalog(tools)
        assert len(catalog) == 2
        # core vs deferred
        sources = {entry.source for entry in catalog}
        assert sources == {"core", "deferred"}


class TestSearchCatalog:
    def test_finds_exact_match(self) -> None:
        catalog = ts.build_catalog(
            [_make_tool("x", "Reads file contents")]
        )
        results = ts.search_catalog(catalog, "x")
        assert any(r.name == "x" for r in results)

    def test_finds_description_keyword(self) -> None:
        catalog = ts.build_catalog(
            [_make_tool("foo", "Calculates fibonacci numbers")]
        )
        results = ts.search_catalog(catalog, "fibonacci")
        assert len(results) == 1
        assert results[0].name == "foo"

    def test_no_results_for_unrelated(self) -> None:
        catalog = ts.build_catalog(
            [_make_tool("foo", "Calculate")]
        )
        results = ts.search_catalog(catalog, "xyz123nomatch")
        assert results == []

    def test_limit(self) -> None:
        catalog = ts.build_catalog(
            [
                _make_tool(f"tool_{i}", f"does thing {i}")
                for i in range(20)
            ]
        )
        results = ts.search_catalog(catalog, "thing", limit=3)
        assert len(results) == 3


class TestListing:
    def test_empty(self) -> None:
        listing = ts.build_catalog_listing([], budget_chars=200)
        assert "(no deferred tools)" in listing

    def test_short_budget_truncates(self) -> None:
        catalog = ts.build_catalog(
            [_make_tool(f"tool_{i}", f"description {i}" * 30) for i in range(30)]
        )
        listing = ts.build_catalog_listing(catalog, budget_chars=400)
        assert len(listing) <= 600  # some slack for the prefix line


class TestBridgeTools:
    def test_three_bridge_tools(self) -> None:
        bridges = ts.make_bridge_tools()
        names = {b["function"]["name"] for b in bridges}
        assert names == {"tool_search", "tool_describe", "tool_call"}

    def test_bridge_tools_have_schemas(self) -> None:
        for bridge in ts.make_bridge_tools():
            fn = bridge["function"]
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"


class TestFindTool:
    def test_found(self) -> None:
        catalog = ts.build_catalog([_make_tool("foo", "Foo description")])
        result = ts.find_tool_in_catalog(catalog, "foo")
        assert result is not None
        assert result["function"]["name"] == "foo"

    def test_missing(self) -> None:
        catalog = ts.build_catalog([_make_tool("foo", "Foo description")])
        assert ts.find_tool_in_catalog(catalog, "bar") is None
