---
status: done
name: command-job
type: command
phase: C2
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /job

## Zweck
Geplante Jobs im REPL verwalten (CLI-Äquivalent: `eaccode job …`).

## Syntax
```
/job list
/job add <id> --schedule <cron> --prompt <text> [--deliver log|stdout]
/job remove <id>
/job pause <id>
/job resume <id>
/job run <id>
```

## Details
- Jobs liegen in `data/jobs.yaml` (id, schedule, prompt, enabled, deliver,
  last_run/status)
- `run` führt den Prompt via Subprocess aus (`eaccode -p`) und liefert an
  Log-Datei oder stdout
- Cron-Expressionen via APScheduler (v3.10, `>=3.10,<4` — v4 ist Pre-Release)

## Verknüpft
[[15-features/system/cron-daemon.md|cron-daemon]] · [[15-features/commands/README.md|README]]
