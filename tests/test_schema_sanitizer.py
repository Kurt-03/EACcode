"""Tests for schema_sanitizer (Phase G.5, Plan G v5)."""

from __future__ import annotations

import pytest

from eaccode.schema_sanitizer import (
    _sanitize_schema,
    sanitize_property_key,
    sanitize_tool_schemas,
)


class TestSanitizePropertyKey:
    def test_alphanumeric_unchanged(self) -> None:
        assert sanitize_property_key("foo") == "foo"

    def test_digit_prefix_added_underscore(self) -> None:
        assert sanitize_property_key("123foo") == "_123foo"

    def test_dot_replaced(self) -> None:
        assert sanitize_property_key("foo.bar") == "foo_bar"

    def test_space_replaced(self) -> None:
        assert sanitize_property_key("hello world") == "hello_world"

    def test_dash_kept(self) -> None:
        assert sanitize_property_key("foo-bar") == "foo-bar"

    def test_underscore_kept(self) -> None:
        assert sanitize_property_key("foo_bar") == "foo_bar"


class TestShouldSanitize:
    def test_minimax_sanitises(self) -> None:
        assert sanitize_tool_schemas([], provider="minimax") is not None

    def test_anthropic_passes_through(self) -> None:
        tool = {"type": "function", "function": {"name": "x"}}
        # Anthropic is not in strict list, returns the same list (no copy)
        result = sanitize_tool_schemas([tool], provider="anthropic")
        assert result == [tool]


class TestSchemaStripping:
    def test_drops_dollar_ref(self) -> None:
        schema = {
            "type": "object",
            "properties": {"x": {"$ref": "#/definitions/X"}},
        }
        out = _sanitize_schema(schema, path="<tool>")
        assert "$ref" not in out["properties"]["x"]

    def test_drops_const(self) -> None:
        schema = {"type": "object", "properties": {"x": {"const": "y"}}}
        out = _sanitize_schema(schema, path="<tool>")
        assert "const" not in out["properties"]["x"]

    def test_drops_pattern_format_min_max(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "x": {
                    "type": "string",
                    "pattern": "^[a-z]+$",
                    "format": "email",
                    "minLength": 1,
                    "maxLength": 100,
                }
            },
        }
        out = _sanitize_schema(schema, path="<tool>")
        x = out["properties"]["x"]
        for k in ("pattern", "format", "minLength", "maxLength"):
            assert k not in x

    def test_collapses_nullable_type_list(self) -> None:
        schema = {
            "type": "object",
            "properties": {"x": {"type": ["string", "null"]}},
        }
        out = _sanitize_schema(schema, path="<tool>")
        x = out["properties"]["x"]
        assert x["type"] == "string"
        assert x.get("nullable") is True

    def test_drops_top_level_oneOf_anyOf_allOf(self) -> None:
        schema = {
            "type": "object",
            "oneOf": [{"type": "string"}, {"type": "number"}],
            "anyOf": [],
            "allOf": [],
            "properties": {"x": {"type": "string"}},
        }
        out = _sanitize_schema(schema, path="<tool>")
        for k in ("oneOf", "anyOf", "allOf"):
            assert k not in out

    def test_nested_oneOf_is_preserved(self) -> None:
        """Nested oneOf stays in place; only top-level is stripped."""
        schema = {
            "type": "object",
            "properties": {"x": {"oneOf": [{"type": "string"}]}},
        }
        out = _sanitize_schema(schema, path="<tool>")
        # Nested oneOf stays - sanitiser only strips at tool-level root.
        assert "oneOf" in out["properties"]["x"]


class TestPropertyKeyRename:
    def test_renames_illegal_keys(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "user.name": {"type": "string"},
                "x": {"type": "string"},
            },
        }
        out = _sanitize_schema(schema, path="<tool>")
        assert "user_name" in out["properties"]
        assert "x" in out["properties"]


class TestSanitizeToolSchemas:
    def test_empty_list(self) -> None:
        assert sanitize_tool_schemas([], provider="minimax") == []

    def test_passes_through_non_dict(self) -> None:
        assert sanitize_tool_schemas(["not a dict"], provider="minimax") == [
            "not a dict"
        ]

    def test_handles_tool_without_function_key(self) -> None:
        tool = {"name": "x"}
        out = sanitize_tool_schemas([tool], provider="minimax")
        assert out == [tool]

    def test_handles_tool_without_parameters(self) -> None:
        tool = {"type": "function", "function": {"name": "x"}}
        out = sanitize_tool_schemas([tool], provider="minimax")
        assert out == [tool]

    def test_sanitises_multiple(self) -> None:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "x",
                    "parameters": {
                        "type": "object",
                        "properties": {"y": {"const": "z"}},
                    },
                },
            }
        ]
        out = sanitize_tool_schemas(tools, provider="minimax")
        assert "const" not in out[0]["function"]["parameters"]["properties"]["y"]
