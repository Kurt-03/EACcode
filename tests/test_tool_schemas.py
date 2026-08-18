"""Tests for tool-schema completeness (Plan A).

Verifies:
- All tools have mutates tag
- All non-empty parameter schemas include property descriptions
- All required-args are documented (description)
- `returns` info is included in tool description (optional but recommended)
"""

from __future__ import annotations

from typing import Any

from eaccode.agent import Tool
from eaccode.tools import BUILTIN_TOOLS
from eaccode.editing import make_editing_tools
from eaccode.learning import make_learning_tools
from eaccode.memory import make_memory_tools
from eaccode.repo import make_repo_tools
from eaccode.git import make_git_tools
from eaccode.store import make_session_tools
from eaccode.testrunner import make_test_tools
from eaccode.browser import make_browser_tools


def _all_tools() -> list[Tool]:
    return (
        list(BUILTIN_TOOLS)
        + make_editing_tools()
        + make_learning_tools()
        + make_memory_tools()
        + make_repo_tools()
        + make_git_tools()
        + make_session_tools()
        + make_test_tools()
        + make_browser_tools()
    )


def _tools_with_schemas() -> list[Tool]:
    return [t for t in _all_tools() if t.parameters.get("properties")]


class TestTags:
    def test_all_tools_have_mutates(self) -> None:
        # Tag is required for the permission system
        for tool in _all_tools():
            assert hasattr(tool, "mutates"), f"{tool.name} missing mutates"
            assert isinstance(tool.mutates, bool), f"{tool.name}: mutates must be bool"

    def test_write_file_is_mutating(self) -> None:
        wf = next(t for t in _all_tools() if t.name == "write_file")
        assert wf.mutates is True

    def test_read_only_tools_marked_false(self) -> None:
        for tool_name in ("read_file", "list_files", "git_status", "browser_status"):
            t = next(t for t in _all_tools() if t.name == tool_name)
            assert t.mutates is False, f"{tool_name} should be mutates=False"


class TestDescriptions:
    def test_no_empty_descriptions(self) -> None:
        for tool in _all_tools():
            assert tool.description.strip(), f"{tool.name}: empty description"
            assert len(tool.description) > 10, (
                f"{tool.name}: description too short ({tool.description!r})"
            )

    def test_property_descriptions_populated(self) -> None:
        for tool in _tools_with_schemas():
            for prop_name, prop_schema in tool.parameters.get("properties", {}).items():
                if isinstance(prop_schema, dict):
                    assert "description" in prop_schema, (
                        f"{tool.name}.{prop_name} missing description"
                    )
                    desc = prop_schema["description"]
                    assert desc and len(desc) > 5, (
                        f"{tool.name}.{prop_name}: description too short {desc!r}"
                    )


class TestRequiredFields:

    def test_write_file_requires_path_and_content(self) -> None:
        wf = next(t for t in _all_tools() if t.name == "write_file")
        req = wf.parameters.get("required", [])
        assert "path" in req
        assert "content" in req

    def test_session_search_requires_query(self) -> None:
        s = next(t for t in _all_tools() if t.name == "session_search")
        assert "query" in s.parameters.get("required", [])



class TestBrowserTools:
    def test_browser_actions_marked_always_ask(self) -> None:
        # Navigation / interaction -> always-ask because they can submit forms
        for tool in make_browser_tools():
            if tool.mutates:
                assert tool.always_ask, (
                    f"browser mutating tool {tool.name} should always_ask"
                )


class TestGitTools:
    def test_git_commit_mutates(self) -> None:
        gc = next(t for t in _all_tools() if t.name == "git_commit")
        assert gc.mutates is True

    def test_git_read_operations_safe(self) -> None:
        for tool_name in ("git_status", "git_log", "git_diff"):
            t = next(t for t in _all_tools() if t.name == tool_name)
            assert t.mutates is False


class TestMemoryTools:
    def test_all_memory_mutating(self) -> None:
        for tool in make_memory_tools():
            assert tool.mutates, f"memory tool {tool.name} should be mutating"

    def test_target_enum_documented(self) -> None:
        for tool in make_memory_tools():
            target = tool.parameters.get("properties", {}).get("target")
            if isinstance(target, dict):
                assert "description" in target, (
                    f"{tool.name}: target property missing description"
                )
                assert target.get("enum") == ["agent", "user"]


class TestEditingTools:
    def test_undo_edit_is_mutating(self) -> None:
        ue = next(t for t in _all_tools() if t.name == "undo_edit")
        assert ue.mutates is True
