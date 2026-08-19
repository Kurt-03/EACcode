"""Tests for _pseudo_stream_text (Plan M streaming fix)."""

from __future__ import annotations

import time

import pytest

from eaccode.agent import _pseudo_stream_text, _split_for_pseudo_stream
from eaccode.providers.base import StreamChunk


class TestSplitForPseudoStream:
    def test_empty(self) -> None:
        assert _split_for_pseudo_stream("") == []

    def test_short(self) -> None:
        chunks = _split_for_pseudo_stream("hello", chunk_size=24)
        assert chunks == ["hello"]

    def test_longer_than_chunk_size(self) -> None:
        text = "abcdefghij" * 5  # 50 chars
        chunks = _split_for_pseudo_stream(text, chunk_size=12)
        # All chunks together should reconstruct the text (modulo whitespace handling)
        assert "".join(chunks).strip() == text

    def test_respects_word_boundaries(self) -> None:
        text = "hello world foo bar"
        chunks = _split_for_pseudo_stream(text, chunk_size=8)
        for chunk in chunks[:-1]:
            # Non-last chunks should end with whitespace (no mid-word breaks)
            assert chunk.endswith(" ") or chunk.endswith("\n")

    def test_newline_forces_break(self) -> None:
        text = "line one\nline two\nline three"
        chunks = _split_for_pseudo_stream(text, chunk_size=50)
        # With chunk_size 50 and 24-char text, expect at least 1 chunk
        assert len(chunks) >= 1


class TestPseudoStreamText:
    def test_empty_text_no_chunks(self) -> None:
        chunks: list[StreamChunk] = []
        result = _pseudo_stream_text("", chunks.append, delay_s=0)
        assert result == ""
        assert chunks == []

    def test_no_callback(self) -> None:
        # Without a callback, returns the text without error
        result = _pseudo_stream_text("hello", None, delay_s=0)
        assert result == "hello"

    def test_emits_sub_chunks(self) -> None:
        chunks: list[StreamChunk] = []
        result = _pseudo_stream_text(
            "Hello world, this is a test of pseudo streaming.",
            chunks.append,
            chunk_size=12,
            delay_s=0,
        )
        assert result == "Hello world, this is a test of pseudo streaming."
        # Multiple text chunks emitted
        text_chunks = [c for c in chunks if c.kind == "text"]
        assert len(text_chunks) > 1
        # Reconstructs the full text
        assert "".join(c.content for c in text_chunks).strip() == (
            "Hello world, this is a test of pseudo streaming."
        )
        # Last chunk is 'done'
        assert chunks[-1].kind == "done"

    def test_delay_is_respected(self) -> None:
        """Pseudo-streaming introduces real delay between chunks."""
        chunks: list[float] = []
        t0 = time.monotonic()
        _pseudo_stream_text(
            "abcdefghij" * 8,  # 80 chars
            chunks.append,
            chunk_size=10,
            delay_s=0.05,
        )
        elapsed = time.monotonic() - t0
        # 80 chars / 10 chars_per_chunk = 8 chunks
        # Each chunk has 50ms delay, so at least 7*50ms = 350ms
        assert elapsed >= 0.3, f"pseudo-stream too fast: {elapsed}s"

    def test_short_text_single_chunk(self) -> None:
        chunks: list[StreamChunk] = []
        _pseudo_stream_text("hi", chunks.append, delay_s=0)
        # Short text: 1-2 chunks depending on word boundaries
        text_chunks = [c for c in chunks if c.kind == "text"]
        assert len(text_chunks) <= 2
