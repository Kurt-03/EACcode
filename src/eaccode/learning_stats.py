"""Learning-loop outcome tracking (Plan I P3.15).

Records which skills get injected for which user-prompt sessions,
and whether the agent's final answer was marked successful (exit
without error). Stats live at
``~/.local/share/eaccode/learning/runs.jsonl``.

This module does not change the agent's behaviour; it only measures
it. Future work can use the metrics to improve skill-ranking.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SkillRun:
    """One observation: a session that used (or didn't use) a skill."""
    id: str
    session_id: str
    skill_name: str
    matched: bool
    success: bool
    timestamp: float
    metadata: dict = field(default_factory=dict)


_LEARN_DIR_NAME = "learning"
_LEARN_FILE = "runs.jsonl"
_write_lock = threading.Lock()


def learning_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "eaccode" / _LEARN_DIR_NAME
    return Path.home() / ".local" / "share" / "eaccode" / _LEARN_DIR_NAME


def runs_file() -> Path:
    return learning_dir() / _LEARN_FILE


def record_run(
    session_id: str,
    skill_name: str,
    matched: bool,
    success: bool,
    metadata: Optional[dict] = None,
) -> SkillRun:
    """Record one skill-run observation. Returns the record (also persisted)."""
    run = SkillRun(
        id=uuid.uuid4().hex[:12],
        session_id=session_id,
        skill_name=skill_name,
        matched=matched,
        success=success,
        timestamp=time.time(),
        metadata=metadata or {},
    )
    target = runs_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(run)) + "\n")
    return run


def load_runs(limit: Optional[int] = None) -> list[SkillRun]:
    """Load all runs (or last ``limit``). Newest-first."""
    target = runs_file()
    if not target.exists():
        return []
    out: list[SkillRun] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append(SkillRun(
            id=str(data.get("id", "")),
            session_id=str(data.get("session_id", "")),
            skill_name=str(data.get("skill_name", "")),
            matched=bool(data.get("matched", False)),
            success=bool(data.get("success", False)),
            timestamp=float(data.get("timestamp", 0)),
            metadata=dict(data.get("metadata", {})),
        ))
    out.sort(key=lambda r: r.timestamp, reverse=True)
    if limit is not None:
        out = out[:limit]
    return out


@dataclass
class SkillStats:
    """Aggregated metrics for one skill across all observed runs."""
    skill_name: str
    matched: int
    success: bool
    hit_rate: float
    success_rate: float


def stats_by_skill(limit: Optional[int] = None) -> list[SkillStats]:
    """Return per-skill hit-rate + success-rate."""
    runs = load_runs(limit=limit)
    by_skill: dict[str, list[SkillRun]] = {}
    for r in runs:
        by_skill.setdefault(r.skill_name, []).append(r)
    out: list[SkillStats] = []
    for skill, items in by_skill.items():
        matched = sum(1 for i in items if i.matched)
        success = sum(1 for i in items if i.success)
        n = len(items)
        hit_rate = matched / n if n else 0.0
        success_rate = success / n if n else 0.0
        out.append(SkillStats(
            skill_name=skill,
            matched=matched,
            success=success > 0,
            hit_rate=hit_rate,
            success_rate=success_rate,
        ))
    out.sort(key=lambda s: s.skill_name)
    return out


def clear_runs() -> int:
    """Delete all recorded runs. Returns count removed."""
    target = runs_file()
    if not target.exists():
        return 0
    lines = [ln for ln in target.read_text(encoding="utf-8").splitlines() if ln.strip()]
    target.unlink()
    return len(lines)


__all__ = [
    "SkillRun",
    "SkillStats",
    "learning_dir",
    "runs_file",
    "record_run",
    "load_runs",
    "stats_by_skill",
    "clear_runs",
]