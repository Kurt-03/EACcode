---
name: cmd-skill
type: command
status: done
phase: B1
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /skill

## Zweck
Skill-Registry verwalten (SKILL.md-Dateien im Skill-Verzeichnis).

## Syntax
```
/skill list                        alle Skills + Trigger
/skill view <name>                 volle SKILL.md anzeigen
/skill new <name> --trigger T      Skill-Skelett anlegen
        [--description D]
/skill remove <name>               Skill löschen
```
CLI-Äquivalent: `eaccode skill <cmd>`

## Implementierung
- `src/eaccode/commands.py` — `run_skill_command`
- `src/eaccode/skills.py` — create/list/view/remove, Dedup (Name + Trigger)

## Tests
`tests/test_commands.py` (TestSkillCommands) + `tests/test_skills.py`

## Offene Punkte
- Quote-Parsing für `--description "mehrere Worte"` (Teil der `/`-Überarbeitung)

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/skill-system.md|skill-system]]
