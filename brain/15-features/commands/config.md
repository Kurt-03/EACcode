---
name: cmd-config
type: command
status: done
phase: A2
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /config

## Zweck
Zentrale Konfiguration verwalten (config.yaml) — CLI + REPL gemeinsam.

## Syntax
```
/config init               config.yaml mit Defaults anlegen
/config path               Dateipfad zeigen
/config show               Werte zeigen (Secrets maskiert)
/config get <key>          einen Wert zeigen (Secrets verweigert)
/config set <key> <value>  Wert setzen (Komma → Liste)
/config set-key <key>      Secret via verdecktem Prompt
/config unset <key>        Wert entfernen
```
CLI-Äquivalent: `eaccode config <cmd>`

## Implementierung
- `src/eaccode/commands.py` — `run_config_command` + `USAGE`
- `src/eaccode/config.py` — Pfade, YAML, Masking, `.env`

## Tests
`tests/test_commands.py` (TestConfigCommands) + `tests/test_config.py`

## Offene Punkte
- Quote-Parsing für mehrwortige Werte (Teil der `/`-Überarbeitung)

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/config.md|config.yaml]] · [[adr/0001-config-yaml-design.md|ADR 0001]]
