"""Test for the enriched DEFAULT_SYSTEM_PROMPT (Plan E).

Plan E: model was hallucinating tool names (echo, del, dir) because
the system prompt never told it which tools exist.
"""

from __future__ import annotations

from eaccode.agent import DEFAULT_SYSTEM_PROMPT


class TestSystemPrompt:
    def test_explicitly_lists_eaccode_tools(self) -> None:
        """The prompt must mention eaccode tool names so the model uses them."""
        for tool_name in (
            "list_files",
            "read_file",
            "write_file",
            "patch_file",
            "file_edit",
            "patch_multiple",
            "create_skill",
        ):
            assert tool_name in DEFAULT_SYSTEM_PROMPT, (
                f"system prompt is missing {tool_name}"
            )

    def test_explicitly_prohibits_shell_builtins_as_tool_names(self) -> None:
        """The prompt must say: don't invent echo, del, dir as tool names."""
        for builtin in ("echo", "del", "dir", "ls", "cat"):
            assert builtin in DEFAULT_SYSTEM_PROMPT, (
                f"system prompt is missing mention of {builtin!r}"
            )

    def test_run_command_is_in_prompt(self) -> None:
        # run_command was re-added in Plan I P0.1 - it's the ONE tool that runs shell commands
        assert "run_command" in DEFAULT_SYSTEM_PROMPT
        # It must be called "the ONE tool that runs shell commands"
        assert "ONE" in DEFAULT_SYSTEM_PROMPT or "only" in DEFAULT_SYSTEM_PROMPT.lower()

    def test_workflow_patterns_documented(self) -> None:
        """Hermes-Verbatim: workflow examples the model can copy."""
        # At least one concrete pattern ("show me X" -> read_file etc.)
        for phrase in (
            "Workflow",
            "list_files",
            "read_file",
        ):
            assert phrase in DEFAULT_SYSTEM_PROMPT, (
                f"missing workflow hint {phrase!r}"
            )
