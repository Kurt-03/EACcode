---
name: config.yaml
type: system
status: done
phase: A2
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: config.yaml

## Zweck
Zentrale Konfiguration (`model`, `providers`, `paths`) mit plattformkorrekter
Ablage und sicherem Secret-Handling.

## Implementierung
- `src/eaccode/config.py` — Pfade (manuell, kein platformdirs), YAML
  load/save, Masking, `providers.*` dynamisch, `.env`-Loading
- `src/eaccode/commands.py` — `config init/path/show/get/set/set-key/unset`
  (CLI + `/config …`)

## Kommandos
```
/config init · /config show · /config set model.default <m>
/config set-key providers.<name>.api_key
```

## Entscheidungen
- [[ADR/0001-config-yaml-design.md|0001-config-yaml-design]] — Design + verworfenes platformdirs

## Tests
`tests/test_config.py` + `tests/test_commands.py` (TestConfig/TestMemory…)

## Offene Punkte
- (keine)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/secrets.md|Secrets]] · [[15-features/system/model-router.md|Model Router]]

## Code-Graph (generiert)

- `src/eaccode/config.py` → —

