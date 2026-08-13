---
name: skill-system
type: system
status: done
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

## Verifiziert (live, 2026-08-13)
- Agent hat `zeit-helfer` selbst per `create_skill` angelegt (B2-DoD)
- Trigger `uhrzeit` matchte → Skill injiziert → Agent nutzte `current_time`

## Tests
`tests/test_skills.py` (21) + Injection-Tests in `tests/test_agent.py`

## Offene Punkte (Hermes-Vergleich 2026-08-13)
- Skill-Kategorien + Pinning (Hermes-Struktur)
- Linked Files (references/scripts/templates) + `skill_view`-Tool für den Agent
- Skill-Index-Injection (Descriptions) statt Body-Injection bei vielen Skills
- Curator/Pruning mit Konsolidierung (`absorbed_into`-Stil)
- Skill-Templates + Variablen-Substitution
- Regex-Trigger + Prioritäten
- Quote-Parsing für `/skill new --description "mehrere Worte"` (Teil der
  geplanten `/`-Commands-Überarbeitung)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/learning-loop.md|learning-loop]]

## Code-Graph (generiert)

- `src/eaccode/skills.py` → [[15-features/system/config.md|Config]]

