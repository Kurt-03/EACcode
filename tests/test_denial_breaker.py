"""Tests for denial_breaker (Phase G.11, Plan G v4, H5/H6)."""

from __future__ import annotations

import pytest

from eaccode import denial_breaker as db


@pytest.fixture
def breaker() -> db.DenialBreaker:
    return db.DenialBreaker(threshold=3)


class TestRecord:
    def test_record_increments(self, breaker) -> None:
        assert breaker.record("s1") == 1
        assert breaker.record("s1") == 2
        assert breaker.record("s1") == 3

    def test_record_separate_sessions(self, breaker) -> None:
        assert breaker.record("s1") == 1
        assert breaker.record("s2") == 1
        assert breaker.record("s1") == 2
        assert breaker.record("s2") == 2


class TestReset:
    def test_reset_clears(self, breaker) -> None:
        breaker.record("s1")
        breaker.record("s1")
        assert breaker.count("s1") == 2
        breaker.reset("s1")
        assert breaker.count("s1") == 0

    def test_reset_missing_is_silent(self, breaker) -> None:
        breaker.reset("never_seen")  # no error


class TestAddendum:
    def test_below_threshold_empty(self, breaker) -> None:
        breaker.record("s1")
        breaker.record("s1")
        assert breaker.addendum("s1") == ""

    def test_at_threshold_returns_text(self, breaker) -> None:
        for _ in range(3):
            breaker.record("s1")
        text = breaker.addendum("s1")
        assert "Denial-breaker tripped" in text
        assert "3" in text

    def test_above_threshold_still_text(self, breaker) -> None:
        for _ in range(5):
            breaker.record("s1")
        text = breaker.addendum("s1")
        assert "5" in text

    def test_disabled_threshold_returns_empty(self) -> None:
        breaker = db.DenialBreaker(threshold=0)
        for _ in range(10):
            breaker.record("s1")
        assert breaker.addendum("s1") == ""


class TestThreshold:
    def test_set_threshold(self, breaker) -> None:
        breaker.set_threshold(5)
        assert breaker.threshold == 5
        for _ in range(4):
            breaker.record("s1")
        assert breaker.addendum("s1") == ""
        breaker.record("s1")
        assert "5" in breaker.addendum("s1")

    def test_set_threshold_zero_disables(self, breaker) -> None:
        breaker.set_threshold(0)
        for _ in range(50):
            breaker.record("s1")
        assert breaker.addendum("s1") == ""

    def test_negative_threshold_normalised_to_zero(self, breaker) -> None:
        breaker.set_threshold(-5)
        assert breaker.threshold == 0


class TestLruEviction:
    def test_evicts_oldest_when_full(self) -> None:
        breaker = db.DenialBreaker(threshold=3, max_sessions=2)
        breaker.record("a")
        breaker.record("b")
        breaker.record("a")  # makes 'a' most-recent, 'b' oldest
        breaker.record("c")  # triggers eviction of 'b'
        # 'b' should have been dropped
        assert breaker.count("b") == 0
        # 'a' and 'c' still tracked
        assert breaker.count("a") == 2
        assert breaker.count("c") == 1


class TestModuleLevel:
    def test_singleton_exists(self) -> None:
        assert db.DEFAULT_DENIAL_BREAKER is not None
        assert db.get_denial_breaker() is db.DEFAULT_DENIAL_BREAKER
