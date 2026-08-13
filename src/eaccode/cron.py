"""Cron & daemon (Phase C2): scheduled jobs with APScheduler.

Jobs live in ``data/jobs.yaml`` (id, schedule, prompt, enabled). A job runs
``eaccode -p <prompt>`` as a subprocess and delivers the output to its log
file (``data/jobs/<id>.log``). ``eaccode daemon`` schedules all enabled jobs.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from eaccode import config as cfg


@dataclass
class Job:
    id: str
    schedule: str  # cron expression, e.g. "0 9 * * *"
    prompt: str
    enabled: bool = True
    last_run: str | None = None
    last_status: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Job:
        return cls(
            id=str(data.get("id", "")),
            schedule=str(data.get("schedule", "")),
            prompt=str(data.get("prompt", "")),
            enabled=bool(data.get("enabled", True)),
            last_run=data.get("last_run"),
            last_status=data.get("last_status"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "schedule": self.schedule,
            "prompt": self.prompt,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "last_status": self.last_status,
        }


def jobs_path() -> Path:
    return cfg.data_dir() / "jobs.yaml"


def _lock() -> threading.Lock:
    return threading.Lock()


def load_jobs() -> list[Job]:
    path = jobs_path()
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    except yaml.YAMLError:
        return []
    return [Job.from_dict(item) for item in data if isinstance(item, dict)]


def _save_jobs(jobs: list[Job]) -> None:
    path = jobs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [job.to_dict() for job in jobs]
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def add_job(job_id: str, schedule: str, prompt: str) -> str:
    """Add a job; errors on duplicate ids and invalid cron expressions."""
    job_id = job_id.strip()
    if not job_id or not schedule or not prompt:
        return "Error: id, schedule and prompt are required"
    _validate_schedule(schedule)
    jobs = load_jobs()
    if any(job.id == job_id for job in jobs):
        return f"Error: job already exists: {job_id}"
    jobs.append(Job(id=job_id, schedule=schedule, prompt=prompt))
    _save_jobs(jobs)
    return f"job '{job_id}' added"


def remove_job(job_id: str) -> str:
    jobs = load_jobs()
    kept = [job for job in jobs if job.id != job_id]
    if len(kept) == len(jobs):
        return f"Error: no job with id: {job_id}"
    _save_jobs(kept)
    return f"job '{job_id}' removed"


def set_enabled(job_id: str, enabled: bool) -> str:
    jobs = load_jobs()
    for job in jobs:
        if job.id == job_id:
            job.enabled = enabled
            _save_jobs(jobs)
            state = "paused" if not enabled else "resumed"
            return f"job '{job_id}' {state}"
    return f"Error: no job with id: {job_id}"


def _validate_schedule(schedule: str) -> None:
    from apscheduler.triggers.cron import CronTrigger

    try:
        CronTrigger.from_crontab(schedule)
    except ValueError as exc:
        raise ValueError(f"invalid cron expression '{schedule}': {exc}") from exc


def job_log_path(job_id: str) -> Path:
    return cfg.data_dir() / "jobs" / f"{job_id}.log"


def _deliver(job_id: str, output: str, status: str) -> None:
    path = job_log_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"--- {timestamp} [{status}] ---\n{output}\n")
    print(f"[cron:{job_id}] {status} — {timestamp}")


def run_job(job: Job) -> str:
    """Execute one job via subprocess; returns the output."""
    result = subprocess.run(
        [sys.executable, "-m", "eaccode", "-p", job.prompt],
        capture_output=True,
        text=True,
        timeout=600,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    status = "ok" if result.returncode == 0 else f"exit {result.returncode}"
    _deliver(job.id, output, status)
    return output


def run_job_by_id(job_id: str) -> str:
    """Run a stored job now (used by `eaccode job run <id>`)."""
    job = next((j for j in load_jobs() if j.id == job_id), None)
    if job is None:
        return f"Error: no job with id: {job_id}"
    if not job.prompt:
        return f"Error: job '{job_id}' has no prompt"
    output = run_job(job)
    jobs = load_jobs()
    for stored in jobs:
        if stored.id == job_id:
            stored.last_run = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            stored.last_status = "ok"
            break
    _save_jobs(jobs)
    return output


def make_scheduler() -> Any:
    """APScheduler with all enabled jobs attached (daemon entry point)."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    scheduler = BlockingScheduler()
    for job in load_jobs():
        if not job.enabled:
            continue
        from apscheduler.triggers.cron import CronTrigger

        scheduler.add_job(
            run_job_by_id,
            trigger=CronTrigger.from_crontab(job.schedule),
            args=[job.id],
            id=f"cron-{job.id}",
            replace_existing=True,
            misfire_grace_time=60,
        )
    return scheduler
