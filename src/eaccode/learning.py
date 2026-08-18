"""Learning loop (Phase B2): agent tools to create and improve skills.

The agent reviews complex tasks after the fact and — when something
recurring appears — creates or improves a skill itself. Deduplication:
same name -> refused (use improve_skill), same trigger -> refused.
"""

from __future__ import annotations

from eaccode import skills
from eaccode.agent import Tool

LEARNING_PROMPT = """\
## Learning loop (important)

After complex or recurring tasks, consider whether a reusable skill would
help. Skills live in a registry with a trigger phrase; they are injected
when the user's message matches.

- Use create_skill when you discovered a repeatable procedure.
- Use improve_skill to update an existing skill's body (never create a
  duplicate — check list_skills first).
- Keep skills short, concrete and actionable (markdown, max ~40 lines).
- Do NOT create skills for trivial one-off tasks.
"""

SCHEMA_NAME = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Skill slug-name (lowercase, dashes for spaces).",
        },
    },
    "required": ["name"],
}
SCHEMA_NAME_DESC = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Skill slug-name (lowercase, dashes for spaces).",
        },
        "description": {
            "type": "string",
            "description": (
                "Short human description of when the skill applies. "
                "Used by the palette to surface matches."
            ),
        },
        "trigger": {
            "type": "string",
            "description": "Phrase the user can type to load the skill.",
        },
        "body": {
            "type": "string",
            "description": (
                "Markdown body of the skill (instructions, examples). "
                "Empty for stubs you later fill via improve_skill."
            ),
        },
    },
    "required": ["name", "description", "trigger"],
}
SCHEMA_NAME_BODY = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "Skill slug-name (existing).",
        },
        "body": {
            "type": "string",
            "description": (
                "Markdown body replacement. The old body is dropped; "
                "trigger stays."
            ),
        },
    },
    "required": ["name", "body"],
}


def _tool_create_skill(name: str, description: str, trigger: str, body: str = "") -> str:
    try:
        skills.create_skill(name, description, trigger, body)
    except skills.SkillError as exc:
        return f"Error: {exc}"
    return f"skill '{name}' created (trigger: {trigger})"


def _tool_improve_skill(name: str, body: str) -> str:
    try:
        skills.update_skill(name, body)
    except skills.SkillError as exc:
        return f"Error: {exc}"
    return f"skill '{name}' updated"


def _tool_list_skills() -> str:
    registry = skills.list_skills()
    if not registry:
        return "(no skills yet - create one with create_skill)"
    return "\n".join(
        f"- {s.name}: {s.description} [trigger: {s.trigger}]" for s in registry
    )


def make_learning_tools() -> list[Tool]:
    """Return the learning-loop tools for the agent."""
    return [
        Tool(
            "create_skill",
            "Create a reusable skill. Returns 'skill <name> created "
            "(trigger: <trigger>)' on success, 'Error: ...' on duplicate "
            "or invalid name/empty trigger. Skills persist under "
            "~/AppData/Local/eaccode/skills.",
            _tool_create_skill,
            SCHEMA_NAME_DESC,
            mutates=True,
        ),
        Tool(
            "improve_skill",
            "Replace the body of an existing skill (trigger + name kept). "
            "Returns 'skill <name> updated' on success, 'Error: not "
            "found' or 'Error: parse failed' on validation failure.",
            _tool_improve_skill,
            SCHEMA_NAME_BODY,
            mutates=True,
        ),
        Tool(
            "list_skills",
            "List all existing skills (markdown bullets: '- <name>: <desc> "
            "[trigger: <trigger>]'). Returns '(no skills yet - ...)' when "
            "empty.",
            _tool_list_skills,
            SCHEMA_NAME,
            mutates=False,
        ),
    ]
