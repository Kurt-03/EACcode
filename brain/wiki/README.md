# Wiki — LLM-gepflegte Wissensseiten

Ab Phase B (Learning-Loop) pflegt eaccode selbst Seiten in diesem Bereich:
Entities, Konzepte, Querverweise — nach dem LLM-Wiki-Muster (Karpathy):
**Wissen wird einmal kompiliert und aktuell gehalten, nicht bei jeder Frage
neu zusammengesucht.**

## Konventionen

- `wiki/` — stabile, verlinkte Wissensseiten (timeless oder dated)
- `wiki/logs/` — datierte Snapshots (`YYYY-MM-DD-titel.md`): was wann passiert ist
- Der Agent **aktualisiert** bestehende Seiten (update statt append) und
  markiert Widersprüche
- Jede Seite: Frontmatter (`date`, `tags`), Wikilinks, Fakten-Regel (siehe
  [[README.md|Vault-Handbuch]])

## Status

- **2026-08-13:** Bereich angelegt — aktive Nutzung ab Phase B
