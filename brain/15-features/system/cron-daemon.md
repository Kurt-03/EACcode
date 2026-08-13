---
name: cron-daemon
type: system
status: done
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
  (id, schedule, prompt, enabled, deliver, last_run/status),
  APScheduler-CronTrigger, `run_job` via subprocess `eaccode -p`,
  Delivery: Log-Datei oder stdout, per Job wählbar
- CLI: `eaccode job list|add|remove|pause|resume|run <id>`
- Daemon: `eaccode daemon` (BlockingScheduler, beendbar per Ctrl+C)
- **Versions-Check 2026-08-13 (Web):** APScheduler 4.0 ist Pre-Release
  („do NOT use"-Hinweis der Maintainer) — Pin `>=3.10,<4` ist korrekt

## Verifiziert (live, 2026-08-13)
- `job add morgen` + `job run` → echter LLM-Call, Antwort „Job läuft",
  Log `[ok]`, last_run gesetzt; remove funktioniert
- **Daemon live**: `eaccode daemon` + Job `* * * * *` → feuerte um 20:01:04,
  Log `[ok] TICK` — voller Kreislauf (Cron → Subprocess → LLM → Log)

## Tests
`tests/test_cron.py` (17: Store, Run, Scheduler, Commands) — inkl. deliver-Ziel

## Offene Punkte
- Delivery-Ziele außer Log/stdout (C4: Telegram)
- Daemon als echter Service (Windows-Dienst/launchd) — später

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/one-shot.md|One-Shot]] · [[15-features/system/permissions.md|permissions]]

## Code-Graph (generiert)

- `src/eaccode/cron.py` → [[15-features/system/config.md|config.yaml]]

