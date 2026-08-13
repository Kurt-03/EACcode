"""Skill system (Phase B1): SKILL.md format, directories, trigger matching.

A skill is a folder ``skills/<name>/SKILL.md`` with YAML frontmatter
(``name``, ``description``, ``trigger``) and a markdown body. Skills are
matched against the user's latest message and injected into the agent's
system prompt (max. 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from eaccode import config as cfg

SKILL_FILE = "SKILL.md"
MAX_INJECT = 3

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


class SkillError(Exception):
    """Raised for skill-system failures (bad frontmatter, duplicates)."""


@dataclass
class Skill:
    name: str
    description: str
    trigger: str
    body: str = ""
    path: Path | None = None
    tags: list[str] = field(default_factory=list)


def skill_dir() -> Path:
    """Directory holding all skills (data dir / skills)."""
    return cfg.data_dir() / "skills"


def skill_path(name: str) -> Path:
    """Path to a skill's SKILL.md; validates the name."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-_]*", name):
        raise SkillError(
            f"invalid skill name: {name!r} (lowercase letters, digits, - and _)"
        )
    return skill_dir() / name / SKILL_FILE


def parse_skill(text: str, path: Path | None = None) -> Skill:
    """Parse a SKILL.md: YAML frontmatter + markdown body."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise SkillError(f"missing frontmatter in {path or 'skill'}")
    import yaml

    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise SkillError(f"invalid frontmatter in {path or 'skill'}: {exc}") from exc
    name = meta.get("name") or (path.parent.name if path else "")
    if not name:
        raise SkillError(f"skill without name: {path}")
    return Skill(
        name=str(name),
        description=str(meta.get("description", "")),
        trigger=str(meta.get("trigger", "")),
        body=match.group(2).strip(),
        path=path,
        tags=[str(tag) for tag in (meta.get("tags") or [])],
    )


def render_skill(skill: Skill) -> str:
    """Serialize a skill back to SKILL.md."""
    tags = "\n".join(f"  - {tag}" for tag in skill.tags)
    tags_line = f"\ntags:\n{tags}" if tags else ""
    return (
        "---\n"
        f"name: {skill.name}\n"
        f"description: {skill.description}\n"
        f"trigger: {skill.trigger}"
        f"{tags_line}\n"
        "---\n"
        f"\n{skill.body.strip()}\n"
    )


def list_skills() -> list[Skill]:
    """Scan the skills directory and parse every SKILL.md (sorted by name)."""
    root = skill_dir()
    if not root.exists():
        return []
    skills: list[Skill] = []
    for candidate in sorted(root.iterdir()):
        file = candidate / SKILL_FILE
        if not file.is_file():
            continue
        try:
            skills.append(parse_skill(file.read_text(encoding="utf-8"), file))
        except (OSError, SkillError):
            continue  # a broken skill must not break the whole registry
    return skills


def create_skill(
    name: str,
    description: str,
    trigger: str,
    body: str = "",
    *, force: bool = False,
) -> Skill:
    """Create a new skill on disk. Raises SkillError on duplicates or bad name."""
    target = skill_path(name)
    if target.exists() and not force:
        raise SkillError(
            f"skill '{name}' already exists - use improve_skill to update it"
        )
    existing = find_by_trigger(trigger)
    if existing and existing.name != name:
        raise SkillError(
            f"trigger {trigger!r} is already used by skill '{existing.name}'"
        )
    skill = Skill(name=name, description=description, trigger=trigger, body=body)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_skill(skill), encoding="utf-8")
    except OSError as exc:
        raise SkillError(f"cannot write skill: {exc}") from exc
    return skill


def update_skill(name: str, body: str) -> Skill:
    """Replace the body of an existing skill; keeps name/description/trigger."""
    target = skill_path(name)
    if not target.exists():
        raise SkillError(f"skill '{name}' does not exist")
    try:
        skill = parse_skill(target.read_text(encoding="utf-8"), target)
    except OSError as exc:
        raise SkillError(f"cannot read skill: {exc}") from exc
    skill.body = body.strip()
    try:
        target.write_text(render_skill(skill), encoding="utf-8")
    except OSError as exc:
        raise SkillError(f"cannot write skill: {exc}") from exc
    return skill


def remove_skill(name: str) -> str:
    """Delete a skill folder; returns a confirmation."""
    target = skill_path(name)
    if not target.exists():
        raise SkillError(f"skill '{name}' does not exist")
    try:
        import shutil

        shutil.rmtree(target.parent)
    except OSError as exc:
        raise SkillError(f"cannot remove skill: {exc}") from exc
    return f"skill '{name}' removed"


def find_by_trigger(trigger: str) -> Skill | None:
    """Return the first skill whose trigger is a substring of ``trigger``."""
    trigger = trigger.strip().lower()
    for skill in list_skills():
        if skill.trigger and skill.trigger.lower() in trigger:
            return skill
    return None


def match_skills(text: str, limit: int = MAX_INJECT) -> list[Skill]:
    """Match a message against all skill triggers (case-insensitive substring)."""
    text = text.lower()
    hits = [s for s in list_skills() if s.trigger and s.trigger.lower() in text]
    return hits[:limit]


def injection_block(text: str) -> str:
    """Build the system-prompt block for skills matching ``text``."""
    hits = match_skills(text)
    if not hits:
        return ""
    blocks = [
        f"### {skill.name} — {skill.description}\n{skill.body}" for skill in hits
    ]
    return "\n\n## Relevant skills (use them!)\n" + "\n\n".join(blocks)
