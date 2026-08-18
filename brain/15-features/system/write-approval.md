---
name: write-approval
type: system
status: done
phase: 08-18 plan-h-stufe-2
date: 2026-08-18
tags: [type/feature, feature/system, hermes]
---

# Write Approval — Stage-Pending für Memory und Skills (Plan H Stufe 2)

> Hermes-Verbatim analog von `tools/write_approval.py` (494 LOC). Cross-session
> Writes (Memory, Skills) werden gestaged und nicht sofort persistiert.

## Zweck

Memory- und Skill-Writes sind cross-session persistent — wenn ein Agent sie
im Hintergrund schreibt, hat der User keine Chance mehr, sie zu reviewen.
`write_approval.py` ist die Hermes-Lösung: Write wird in
`~/.local/share/eaccode/pending/<subsystem>/<id>.json` gestaged, der User
kann später approven oder verwerfen.

## Staged Subsystems

```python
STAGED_SUBSYSTEMS = ("memory", "skills")
```

Jeder andere Subsystem raised `ValueError("unknown subsystem")` — das macht
die API schwer fehlnutzbar.

## PendingWrite-Record

```python
@dataclass
class PendingWrite:
    id: str                # uuid hex (8 chars)
    subsystem: str         # "memory" oder "skills"
    action: str            # payload.action
    summary: str           # Human-readable summary (gesehen vom User)
    origin: str            # "foreground" (manuell) oder andere
    created_at: float      # unix timestamp
    payload: dict          # full action + args (replayable)
```

Atomic Write via temp-file + `os.replace` — kein Crash-Half-State.

## API

| Funktion | Was sie tut |
|---|---|
| `pending_dir(subsystem)` | Path zur Pending-Directory (Windows: `%LOCALAPPDATA%/eaccode/pending/...`) |
| `stage_write(subsystem, payload, *, summary, origin)` | Persist + return PendingWrite |
| `list_pending(subsystem)` | newest-first sortiert |
| `get_pending(subsystem, pid)` | Single record oder None |
| `discard_pending(subsystem, pid)` | Remove single, return True/False |
| `pending_count(subsystem)` | Count |
| `clear_pending(subsystem)` | Remove all, return removed count |

## Approval-Flow (Hermes analog)

1. Agent ruft `memory_add(...)` auf
2. Statt direkt zu schreiben: `stage_write("memory", {"action": "add", ...})`
3. User sieht in TUI eine Liste → `[a] approve / [d] discard`
4. Bei approve: eigentlicher Schreibvorgang läuft mit dem gestagten Payload
5. Bei discard: pending file weg, kein Memory-Effekt

## Tests

`tests/test_write_approval.py` — Stage, List, Get, Discard, Clear, Unknown
Subsystem, Atomic-Write, Custom pending_dir override (monkeypatch).

## Verknüpft
[[15-features/system/memory.md|Memory]] · [[15-features/system/skill-system.md|skill-system]] · [[15-features/system/workspace.md|workspace]]

Plan: `.hermes/plans/2026-08-18_213000-stufe-2-permission-bridge.md`
Hermes source: `_ref/hermes/tools/write_approval.py` (494 lines)

## Code-Graph (generiert)

- `src/eaccode/write_approval.py` → —

