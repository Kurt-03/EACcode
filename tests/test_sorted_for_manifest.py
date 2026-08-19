"""Tests for sorted_for_manifest (Plan L L.4)."""

from __future__ import annotations

import pytest

from eaccode.agent import Tool
from eaccode.tools import sorted_for_manifest


def _t(name: str, mutates: bool) -> Tool:
    return Tool(name, f"Test tool {name}", lambda: None, {"type": "object", "properties": {}}, mutates=mutates)


class TestSortedForManifest:
    def test_readonly_come_first(self) -> None:
        """Read-only tools appear before mutating tools in the sorted list."""
        tools = [
            _t("write_file", mutates=True),
            _t("read_file", mutates=False),
            _t("patch_file", mutates=True),
            _t("list_files", mutates=False),
        ]
        result = [t.name for t in sorted_for_manifest(tools)]
        # First two are read-only (alphabetical), last two are mutating
        assert result[:2] == sorted(["list_files", "read_file"])
        assert result[2:] == sorted(["patch_file", "write_file"])

    def test_alphabetical_within_groups(self) -> None:
        tools = [_t(f"tool_{n}", mutates=(n % 2 == 0)) for n in range(10)]
        result = [t.name for t in sorted_for_manifest(tools)]
        readonly = result[:5]
        mutating = result[5:]
        assert readonly == sorted(readonly)
        assert mutating == sorted(mutating)

    def test_empty(self) -> None:
        assert sorted_for_manifest([]) == []

    def test_only_readonly(self) -> None:
        tools = [_t("a", False), _t("b", False)]
        names = [t.name for t in sorted_for_manifest(tools)]
        assert names == ["a", "b"]

    def test_only_mutating(self) -> None:
        tools = [_t("a", True), _t("b", True)]
        names = [t.name for t in sorted_for_manifest(tools)]
        assert names == ["a", "b"]

    def test_default_uses_builtin(self) -> None:
        """When called without arg, uses BUILTIN_TOOLS."""
        result = sorted_for_manifest()
        assert len(result) > 0
        # No mutating tool before any read-only tool
        seen_mutating = False
        for t in result:
            if t.mutates:
                seen_mutating = True
            else:
                assert not seen_mutating, (
                    f"read-only {t.name} appears after a mutating tool"
                )
