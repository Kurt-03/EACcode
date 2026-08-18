"""Tests for human_wait_window ContextVar (Phase C.3)."""

from __future__ import annotations

from eaccode.human_wait_window import human_wait_window, is_human_wait_active


class TestBasic:
    def test_default_inactive(self) -> None:
        assert is_human_wait_active() is False

    def test_active_inside_window(self) -> None:
        with human_wait_window():
            assert is_human_wait_active() is True

    def test_inactive_after_window(self) -> None:
        with human_wait_window():
            pass
        assert is_human_wait_active() is False

    def test_nested_windows(self) -> None:
        with human_wait_window():
            assert is_human_wait_active() is True
            with human_wait_window():
                assert is_human_wait_active() is True
            # Outer window still active
            assert is_human_wait_active() is True
        assert is_human_wait_active() is False


class TestExceptionSafety:
    def test_deactivates_on_exception(self) -> None:
        try:
            with human_wait_window():
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        # ContextVar should reset even on exception
        assert is_human_wait_active() is False
