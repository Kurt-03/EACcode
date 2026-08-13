---
name: learning-loop
type: system
status: active
phase: B2
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Learning-Loop (B2)

## Zweck
Der Agent bewertet nach komplexen Tasks selbst, ob ein Skill entsteht —
erstellt und verbessert ihn über Tools. Das ist das Herz von
"self-improving".

## Implementierung
- `src/eaccode/learning.py` — Agent-Tools: `create_skill`, `improve_skill`,
  `list_skills` (Dedup-Sicht)
- Dedup: gleicher Name → Verweigerung (Verbesserung nutzen); gleicher
  Trigger bei anderem Namen → Warnung
- System-Prompt-Zusatz: Post-Task-Review-Anweisung
- `/skill`-Kommandos für den User (B1)

## Tests
`tests/test_learning.py`

## Offene Punkte
- Automatisches Pruning (Dedup über alle Skills)
- Skill-Nutzungs-Statistik (welche Skills greifen wann)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/skill-system.md|Skill-System]]
