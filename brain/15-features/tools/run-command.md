---
name: run-command
type: tool
status: done
phase: 08-18 plan-i-p0.1
date: 2026-08-18
tags: [type/feature, feature/tool, shell, coding-agent]
---

# run_command

> Echtes Shell-Tool (Plan I P0.1, re-added nach User-Request).

## Was es macht

Führt Shell-Commands aus (Windows cmd.exe / POSIX sh), mit:
- Working-Directory-Management (relativ zu workspace-root)
- Timeout (default 60s, max 600s)
- Output-Capture (stdout+stderr combined)
- Exit-Code-Surface ("(exit N)" prefix)
- Permission-Gate (Smart-Mode Aux-LLM für gefährliche commands, Hardline-Block für sudo -S etc.)

## Container-Opt-In

`EACCODE_RUN_IN_CONTAINER=1` aktiviert Docker-Modus:
- Command läuft in einem frischen Container (python:3.11-slim default)
- Workspace wird als `/workspace` gemountet
- Container wird nach dem Command gestoppt

## Live-Verify

```bash
$ eaccode -p "run pytest"
→ tests run, output captured

$ eaccode -p "run sudo -S rm -rf /"
→ "Error: hardline pattern matched"

$ EACCODE_RUN_IN_CONTAINER=1 eaccode -p "run pytest in /workspace"
→ docker container started, tests run, container stopped
```

## History

- **08-18 v1**: Erste Implementation mit subprocess.run(shell=True)
- **08-18 v2 (Plan H)**: Entfernt (User wollte Sandbox-Workspace statt shell-Access)
- **08-18 v3 (Plan I P0.1)**: Wieder hinzugefügt mit Container-Opt-In

## Reference

- Code: `src/eaccode/tools.py::run_command`
- Tests: `tests/test_run_command.py`
- Container: `src/eaccode/container.py`