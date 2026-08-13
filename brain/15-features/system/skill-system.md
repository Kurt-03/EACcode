---
name: skill-system
type: system
status: active
phase: B1
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Skill-System (B1)

## Zweck
Wiederverwendbares Wissen als Markdown-Skills: SKILL.md mit Frontmatter
(name/description/trigger), Skill-Verzeichnisse, Laden per Trigger in den
Agent-Kontext.

## Implementierung
- `src/eaccode/skills.py` — Skill-Dataclass, Frontmatter-Parser, Verzeichnis-
  Scan, `create/list/view/remove`, Trigger-Matching (substring, case-insens.)
- Skill = `data/skills/<name>/SKILL.md` (+ optional `scripts/`, `references/`)
- Kommandos: `/skill list|view|new|remove`
- Injection: gematchte Skills werden beim Agent-Run an den System-Prompt
  angehängt (max. 3)

## Tests
`tests/test_skills.py`

## Offene Punkte
- Skill-Templates + Variablen-Substitution (B2/B)
- Regex-Trigger + Prioritäten

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/learning-loop.md|Learning-Loop]]
