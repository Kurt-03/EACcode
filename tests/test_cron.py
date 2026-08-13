"""Tests for cron & daemon (Phase C2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from eaccode import config as cfg
from eaccode import cron


@pytest.fixture
def tmp_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    return tmp_path


class TestJobStore:
    def test_add_and_load(self, tmp_jobs: Path) -> None:
        assert "added" in cron.add_job("daily", "0 9 * * *", "guten morgen")
        jobs = cron.load_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "daily"
        assert jobs[0].schedule == "0 9 * * *"

    def test_add_duplicate_rejected(self, tmp_jobs: Path) -> None:
        cron.add_job("daily", "0 9 * * *", "x")
        assert "already exists" in cron.add_job("daily", "0 9 * * *", "y")

    def test_add_invalid_cron_rejected(self, tmp_jobs: Path) -> None:
        with pytest.raises(ValueError):
            cron.add_job("kaputt", "99 99 * * *", "x")

    def test_add_requires_fields(self, tmp_jobs: Path) -> None:
        assert "required" in cron.add_job("", "0 9 * * *", "x")

    def test_remove(self, tmp_jobs: Path) -> None:
        cron.add_job("a", "0 9 * * *", "x")
        cron.add_job("b", "0 9 * * *", "y")
        assert "removed" in cron.remove_job("a")
        assert [j.id for j in cron.load_jobs()] == ["b"]
        assert "no job" in cron.remove_job("ghost")

    def test_pause_resume(self, tmp_jobs: Path) -> None:
        cron.add_job("a", "0 9 * * *", "x")
        assert "paused" in cron.set_enabled("a", False)
        assert not cron.load_jobs()[0].enabled
        assert "resumed" in cron.set_enabled("a", True)
        assert cron.load_jobs()[0].enabled

    def test_persists_across_reload(self, tmp_jobs: Path) -> None:
        cron.add_job("a", "*/5 * * * *", "tick")
        reloaded = cron.load_jobs()
        assert reloaded[0].prompt == "tick"


class TestRunJob:
    def test_run_job_by_id(self, tmp_jobs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cron.add_job("hello", "0 9 * * *", "sag hallo")

        def fake_run(command: list[str], **kwargs: Any) -> Any:
            import subprocess

            assert "-m" in command and "eaccode" in command
            return subprocess.CompletedProcess(command, 0, stdout="hallo welt\n", stderr="")

        monkeypatch.setattr(cron.subprocess, "run", fake_run)
        output = cron.run_job_by_id("hello")
        assert output == "hallo welt"
        log = cron.job_log_path("hello").read_text(encoding="utf-8")
        assert "hallo welt" in log
        assert "[ok]" in log
        jobs = cron.load_jobs()
        assert jobs[0].last_run is not None
        assert jobs[0].last_status == "ok"

    def test_run_unknown_job(self, tmp_jobs: Path) -> None:
        assert "no job" in cron.run_job_by_id("ghost")

    def test_run_job_failure_logged(self, tmp_jobs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cron.add_job("fails", "0 9 * * *", "kaputt")

        def fake_run(command: list[str], **kwargs: Any) -> Any:
            import subprocess

            return subprocess.CompletedProcess(command, 1, stdout="", stderr="boom")

        monkeypatch.setattr(cron.subprocess, "run", fake_run)
        cron.run_job_by_id("fails")
        log = cron.job_log_path("fails").read_text(encoding="utf-8")
        assert "[exit 1]" in log
        assert "boom" in log


class TestScheduler:
    @staticmethod
    def _shutdown(scheduler: Any) -> None:
        with __import__("contextlib").suppress(Exception):
            scheduler.shutdown(wait=False)

    def test_make_scheduler_attaches_enabled_jobs(self, tmp_jobs: Path) -> None:
        cron.add_job("enabled", "0 9 * * *", "x")
        cron.add_job("paused", "0 9 * * *", "y")
        cron.set_enabled("paused", False)
        scheduler = cron.make_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "cron-enabled" in job_ids
        assert "cron-paused" not in job_ids
        self._shutdown(scheduler)

    def test_make_scheduler_empty(self, tmp_jobs: Path) -> None:
        scheduler = cron.make_scheduler()
        assert scheduler.get_jobs() == []
        self._shutdown(scheduler)


class TestJobCommand:
    @pytest.fixture
    def job_runner(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
        monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
        import io

        from eaccode.commands import run_job_command

        def run(*args: str) -> tuple[int, str]:
            stdout = io.StringIO()
            code = run_job_command(list(args), stdout=stdout)
            return code, stdout.getvalue()

        return run

    def test_list_empty(self, job_runner: Any) -> None:
        code, out = job_runner("list")
        assert code == 0
        assert "no jobs yet" in out

    def test_add_and_list(self, job_runner: Any) -> None:
        code, out = job_runner("add", "daily", "--schedule", "0 9 * * *", "--prompt", "hi")
        assert code == 0
        assert "added" in out
        code, out = job_runner("list")
        assert "daily" in out
        assert "enabled" in out

    def test_remove_pause_resume(self, job_runner: Any) -> None:
        job_runner("add", "x", "--schedule", "0 9 * * *", "--prompt", "hi")
        assert "paused" in job_runner("pause", "x")[1]
        assert "resumed" in job_runner("resume", "x")[1]
        assert "removed" in job_runner("remove", "x")[1]

    def test_invalid_cron_errors(self, job_runner: Any) -> None:
        code, out = job_runner("add", "x", "--schedule", "99 99 * * *", "--prompt", "hi")
        assert code == 1
        assert "invalid cron" in out
