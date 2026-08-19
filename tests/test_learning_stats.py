"""Tests for learning_stats (Plan I P3.15)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import learning_stats as ls


@pytest.fixture
def fresh_dir(tmp_path, monkeypatch):
    """Redirect learning_dir to tmp so tests don't pollute."""
    monkeypatch.setattr(ls, "learning_dir", lambda: tmp_path)
    return tmp_path


class TestRecord:
    def test_basic_record(self, fresh_dir) -> None:
        run = ls.record_run("s1", "skill-x", matched=True, success=True)
        assert run.id
        assert run.session_id == "s1"
        assert ls.runs_file().exists()

    def test_persists_to_jsonl(self, fresh_dir) -> None:
        ls.record_run("s1", "skill-x", matched=True, success=False)
        ls.record_run("s2", "skill-x", matched=False, success=False)
        runs = ls.load_runs()
        assert len(runs) == 2


class TestStats:
    def test_no_runs(self, fresh_dir) -> None:
        assert ls.stats_by_skill() == []

    def test_hit_rate(self, fresh_dir) -> None:
        ls.record_run("s1", "skill-x", matched=True, success=False)
        ls.record_run("s2", "skill-x", matched=True, success=False)
        ls.record_run("s3", "skill-x", matched=False, success=False)
        stats = ls.stats_by_skill()
        assert len(stats) == 1
        x = stats[0]
        assert x.skill_name == "skill-x"
        assert x.matched == 2
        assert 0.6 < x.hit_rate < 0.7  # 2/3

    def test_success_rate(self, fresh_dir) -> None:
        ls.record_run("s1", "skill-y", matched=True, success=True)
        ls.record_run("s2", "skill-y", matched=True, success=False)
        stats = ls.stats_by_skill()
        y = next(s for s in stats if s.skill_name == "skill-y")
        assert y.success_rate == 0.5

    def test_multi_skill(self, fresh_dir) -> None:
        ls.record_run("s1", "skill-x", matched=True, success=False)
        ls.record_run("s2", "skill-y", matched=True, success=True)
        stats = ls.stats_by_skill()
        assert {s.skill_name for s in stats} == {"skill-x", "skill-y"}


class TestClear:
    def test_clear_removes_all(self, fresh_dir) -> None:
        ls.record_run("s1", "x", matched=True, success=False)
        ls.record_run("s2", "y", matched=True, success=True)
        n = ls.clear_runs()
        assert n == 2
        assert not ls.runs_file().exists()