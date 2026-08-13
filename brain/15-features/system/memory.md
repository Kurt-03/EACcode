---
name: memory
type: system
status: done
phase: A6/B4
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Memory (MEMORY.md / USER.md)

## Zweck
Persistente, kuratierte Fakten über Sessions hinweg — Hermes-Modell seit B4:
Agent-Tools, Char-Budgets, Konsolidierungs-Zwang, atomic writes.

## Implementierung (B4-Stand)
- `src/eaccode/memory.py`:
  - Einträge **§-delimitiert** (Hermes-Format), Legacy-Migration aus A6-Format
  - **Char-Budgets:** MEMORY.md 2200, USER.md 1375 — `add` über Limit →
    „Consolidate now"-Meldung mit Budget-Angabe
  - `replace` (mehrdeutig → Fehler), `remove`, **`apply_batch`** (all-or-nothing,
    gegen finales Budget — Konsolidieren + Hinzufügen in einem Call)
  - **Atomic writes** (temp + os.replace), Thread-Locks, Duplikat-Schutz
- **Agent-Tools** (B4): `memory_add` / `memory_replace` / `memory_remove` /
  `memory_apply_batch` (target: agent|user) — der Agent kuratiert selbst
- **Nudge:** alle 10 Agent-Runs erinnert der System-Prompt an Memory-Pflege;
  Reset bei memory_*-Tool-Call
- Kommandos: `/memory show|add|user add|remove` (CLI + REPL)

## Verifiziert (live, 2026-08-13)
- Agent merkte sich „Python + Kaffee" selbst → korrekt in **USER.md** (target=user)
- `/memory show` zeigt beide Sektionen im Injection-Format

## Tests
`tests/test_memory.py` (21) + Memory-Tool-Tests + Nudge-Tests (test_agent)

## Offene Punkte (Hermes-Vergleich 2026-08-13)
- ✅ Injection-Scan nachgerüstet (Fences, Anweisungs-Override EN+DE, gefälschte
  Sektionen; add/replace/apply_batch geschützt — one poisoned op rejects batch)
- Drift-Erkennung explizit (Hermes: Fehler statt stillem Überschreiben bei externem Edit)
- Nudge auf LLM-Turns statt Runs zählen
- Externer Memory-Provider (Supermemory-Stil) — nur bei Bedarf
- Konflikt-Auflösung bei parallelen Prozessen (Datei-Lock)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/commands/memory.md|memory]] · [[15-features/system/session-store.md|session-store]]

## Code-Graph (generiert)

- `src/eaccode/memory.py` → [[15-features/system/agent-core.md|Agent Core]] · [[15-features/system/config.md|config.yaml]]

