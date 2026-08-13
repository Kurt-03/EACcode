---
name: cmd-model
type: command
status: done
phase: A3
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /model

## Zweck
Modell-Katalog, Default, Fallback-Chain und Live-Ping verwalten.

## Syntax
```
/model list                          Katalog mit (default)/(fallback)-Markern
/model add <provider/model> [--base-url URL]   eigenes Modell registrieren
/model set-default <provider/model>
/model set-fallback <m1,m2,...>
/model ping <provider/model>         Live-Call (erwartet "pong")
```
CLI-Äquivalent: `eaccode model <cmd>`

## Implementierung
- `src/eaccode/commands.py` — `run_model_command`
- `src/eaccode/router.py` — `model_chain`, `all_model_ids`, `ping_model`

## Tests
`tests/test_commands.py` (TestModelCommands) + `tests/test_router.py`

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/model-router.md|Model Router]]
