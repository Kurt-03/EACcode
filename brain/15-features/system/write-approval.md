---
name: write-approval
type: system
status: done
phase: 08-18 plan-h-v4-stufe-2
date: 2026-08-18
tags: [type/feature, feature/system, hermes, stage-approval]
---

# Write Approval (Stage-Approval)

> Hermes-Verbatim analog of `tools/write_approval.py`.

Memory und Skill writes gehen **erst in pending/**, dann User review.
Persistiert in `~/.local/share/eaccode/pending/<subsystem>/<id>.json`.

## Subsysteme

- `memory` — `memory_add` writes gehen zuerst in `pending/memory/`
- `skills` — `create_skill` writes gehen zuerst in `pending/skills/`

## Workflow

1. Model ruft `memory_add("...")` auf
2. Write wird in `pending/memory/<id>.json` gestaged
3. User review via `/memory pending`
4. User approved → commit; oder `/memory pending discard <id>`

## API

- `stage_write(subsystem, payload, summary)` — neue pending-write
- `list_pending(subsystem)` — alle pending
- `get_pending(subsystem, id)` — eine pending
- `discard_pending(subsystem, id)` — verwerfen
- `pending_count(subsystem)` — Anzahl
- `clear_pending(subsystem)` — alle löschen

## Reference

- Code: `src/eaccode/write_approval.py`
- Tests: `tests/test_write_approval.py`