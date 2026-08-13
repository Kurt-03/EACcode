---
name: secrets
type: system
status: done
phase: A2
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Secret-Handling

## Zweck
API-Keys gehören dem User, bleiben lokal, erscheinen nie im Klartext.

## Regeln (implementiert)
- Eingabe nur über verdeckten Prompt (`/provider set-key`, getpass)
- `chmod 600` auf der config.yaml (best effort auf Windows)
- `config show` maskiert (`sk-***`), zeigt nur `set (file)` / `set (env: VAR)`
- `config get` verweigert Secret-Keys (segmentbasiertes Erkennen, damit
  `api_key_env` kein False-Positive ist)
- `.env`-Unterstützung via `api_key_env` (env gewinnt über file)
- Keys nie als CLI-Argument (Shell-History-Schutz)

## Implementierung
`src/eaccode/config.py` — `mask_secret`, `is_secret_key`, `provider_key_status`,
`resolve_api_key` (env > file)

## Tests
`tests/test_config.py` (TestMasking, TestEnv) + `tests/test_router.py` (TestApiKey)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/config.md|config.yaml]] · [[adr/0001-config-yaml-design.md|ADR 0001]]
