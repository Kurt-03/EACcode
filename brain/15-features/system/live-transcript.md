---
name: live-transcript
type: system
status: done
phase: 08-18 plan-g-v5-g7
date: 2026-08-18
tags: [type/feature, feature/system, subagents, hermes]
---

# Sub-Agent Live Transcript (G.7)

> Jeder Sub-Agent-Run wird live nach `<data>/live-transcripts/<id>/...txt`
> geschrieben, mit Secret-Redaction. REPL rendert live mit.

## Pfad-Schema

```
~/.local/share/eaccode/live-transcripts/<delegation-id>/
    run.txt            # append-only live transcript
    meta.json          # agent_name, parent_id, started_at, model
```

`LIVE_RETENTION_DAYS = 7`. Cleanup-Old-Runs beim Erstellen eines neuen Runs.

## Public API

```python
@dataclass
class TranscriptEntry:
    role: str       # "user" | "assistant" | "tool" | "system"
    content: str    # redacted
    timestamp: float
    tool_call_id: str | None = None

class LiveTranscript:
    def __init__(delegation_id: str)
    def append(entry: TranscriptEntry) -> None
    def tail(n: int = 50) -> list[TranscriptEntry]
    def redact_and_append(raw: str, role: str) -> None
```

## Secret-Redaction

`redact_and_append` rechnet `redact.redact_text(content)` drüber, bevor
geschrieben wird. Per Hermes-Pattern: GitHub PAT, OpenAI key, AWS, JWT, PEM,
Bearer, Slack.

Thread-safety via `_TRANSCRIPT_LOCK`.

## REPL-Streaming

`palette.py:_render_subagent_lines` pollt jede 200 ms nach neuen Lines
und schreibt sie live in den Log (gedimmt). Symbol `⤷` markiert Sub-Output.

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.7
- [[15-features/system/subagents.md|subagents]]
- [[15-features/system/permissions.md|permissions]]
- Hermes source: `_ref/hermes/tools/delegation_live_log.py`

## Tests

`tests/test_live_transcript.py` — Append, Tail, Redaction, Retention, Threading.
