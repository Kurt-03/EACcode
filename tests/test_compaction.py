"""Tests for token_counter + compaction (Plan I P0.4)."""

from __future__ import annotations

import pytest

from eaccode import compaction, token_counter


class TestEstimateTokens:
    def test_empty(self) -> None:
        assert token_counter.estimate_tokens("") == 0

    def test_whitespace_only(self) -> None:
        assert token_counter.estimate_tokens("   \n  ") == 0

    def test_short_text(self) -> None:
        # 4 chars / 4 = 1 token minimum
        assert token_counter.estimate_tokens("hi") >= 1

    def test_approximate(self) -> None:
        # 400 chars / 4 = ~100 tokens
        text = "a" * 400
        assert 95 <= token_counter.estimate_tokens(text) <= 105


class TestEstimateMessageTokens:
    def test_simple_user_message(self) -> None:
        msg = {"role": "user", "content": "hello world"}
        n = token_counter.estimate_message_tokens(msg)
        assert n > 0

    def test_tool_call_message(self) -> None:
        msg = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "read_file", "arguments": '{"path":"x"}'}}
            ],
        }
        n = token_counter.estimate_message_tokens(msg)
        # Should account for the tool name + args
        assert n > 5

    def test_history_total(self) -> None:
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "bye"},
        ]
        assert token_counter.estimate_history_tokens(msgs) > 0


class TestEstimateToolDefinitionsTokens:
    def test_empty(self) -> None:
        assert token_counter.estimate_tool_definitions_tokens([]) == 0

    def test_with_tools(self) -> None:
        tools = [
            {
                "name": "read_file",
                "description": "Read a file from the workspace",
                "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        ]
        n = token_counter.estimate_tool_definitions_tokens(tools)
        assert n > 0


class TestShouldCompact:
    def test_small_history_no_compact(self) -> None:
        msgs = [{"role": "user", "content": "hi"}]
        assert compaction.should_compact(msgs, [], 32_000) is False

    def test_huge_history_compacts(self) -> None:
        # 200K chars / 4 = 50K tokens, way above 80% of 32K
        msgs = [{"role": "user", "content": "a" * 200_000}]
        assert compaction.should_compact(msgs, [], 32_000) is True

    def test_threshold_respected(self) -> None:
        msgs = [{"role": "user", "content": "a" * 10_000}]  # 2500 tokens
        # 60% threshold - 2500 / 32000 = ~8% - no compact
        assert compaction.should_compact(msgs, [], 32_000, threshold=0.6) is False


class TestSelectCompactionWindow:
    def test_short_history_returns_empty_compact(self) -> None:
        msgs = [{"role": "user", "content": "hi"}]
        to_compact, to_keep = compaction.select_compaction_window(msgs, keep_recent=4)
        assert to_compact == []
        assert to_keep == msgs

    def test_long_history_splits(self) -> None:
        msgs = (
            [{"role": "system", "content": "you are helpful"}]
            + [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        )
        to_compact, to_keep = compaction.select_compaction_window(msgs, keep_recent=4)
        # System preserved
        assert to_keep[0]["role"] == "system"
        # 4 most-recent kept
        assert len([m for m in to_keep if m["role"] == "user"]) == 4
        # Older compacted
        assert len(to_compact) > 0


class TestFormatMessagesForSummary:
    def test_basic(self) -> None:
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        text = compaction.format_messages_for_summary(msgs)
        assert "[user] hi" in text
        assert "[assistant] hello" in text

    def test_handles_list_content(self) -> None:
        msgs = [{"role": "user", "content": [{"text": "x"}]}]
        text = compaction.format_messages_for_summary(msgs)
        assert "x" in text

    def test_handles_tool_calls(self) -> None:
        msgs = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "read_file", "arguments": "{}"}}],
            }
        ]
        text = compaction.format_messages_for_summary(msgs)
        assert "[tool_calls: read_file]" in text


class TestSummaryHelpers:
    def test_summarize_prompt_structure(self) -> None:
        prompt = compaction.summarize_prompt("transcript text")
        assert len(prompt) == 1
        assert prompt[0]["role"] == "user"
        assert "transcript text" in prompt[0]["content"]

    def test_make_summary_message(self) -> None:
        msg = compaction.make_summary_message("the summary text")
        assert msg["role"] == "system"
        assert "the summary text" in msg["content"]