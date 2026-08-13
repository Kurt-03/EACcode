---
name: cron-daemon
type: system
status: active
phase: C2
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Cron & Daemon (C2)

## Zweck
Geplante Jobs (Cron-Expressions) + Hintergrund-Daemon: `eaccode daemon`
läuft, feuert Jobs, liefert Ergebnisse (aktuell: Log-Datei, später
Telegram/Discord via C4).

## Implementierung
- `src/eaccode/cron.py` — Job-Definitionen in `data/jobs.yaml`
  (id, schedule, prompt, enabled), APScheduler-CronTrigger,
  `run_job` via subprocess `eaccode -p`, Log in `data/jobs/<id>.log`
- CLI: `eaccode job list|add|remove|pause|resume|run <id>`
- Daemon: `eaccode daemon` (BlockingScheduler, beendbar per Ctrl+C)

## Verifiziert (live, 2026-08-13)
- (wird beim Live-Test ergänzt)

## Tests
`tests/test_cron.py`

## Offene Punkte
- Delivery-Ziele außer Log (C4: Telegram)
- Daemon als echter Service (Windows-Dienst/launchd) — später

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/one-shot.md|One-Shot]] · [[15-features/system/permissions.md|Permissions]]
