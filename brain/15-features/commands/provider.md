---
name: cmd-provider
type: command
status: done
phase: A3
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /provider

## Zweck
BYOK-Provider verwalten (config.yaml `providers`-Sektion).

## Syntax
```
/provider list                          Provider + Key-Status + base_url
/provider add <name> [--base-url URL]
        [--api-key-env VAR]             Key aus Umgebungsvariable
/provider remove <name>
/provider set-key <name>                Key via verdecktem Prompt
```
CLI-Äquivalent: `eaccode provider <cmd>`

## Implementierung
- `src/eaccode/commands.py` — `run_provider_command`, `_parse_flags`
- Keys: getpass, chmod 600, nie als CLI-Argument

## Tests
`tests/test_commands.py` (TestProviderCommands) — inkl. Flag-Validierung

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/model-router.md|Model Router]]
