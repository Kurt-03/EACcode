---
name: file-safety
type: system
status: done
phase: 08-18 plan-d-h2-h14-h15
date: 2026-08-18
tags: [type/feature, feature/system, security, hermes]
---

# File Safety (Hermes-Verbatim, Phase 2 Plan D)

> Hardcoded exact paths + sensitive directory prefixes for "must never be written" checks.

## Hardcoded Exact Paths (H14)

```python
# src/eaccode/file_safety.py:build_write_denied_paths
~/.ssh/authorized_keys
~/.ssh/id_rsa
~/.ssh/id_ed25519
~/.ssh/config
~/.env                            # home-local
PROJECT_ROOT/.env                  # top-level (cwd)
~/.anthropic_oauth.json           # Anthropic PKCE credentials (home + project)
cache/bws_cache.enc.json           # Bitwarden encrypted cache (home + project)
~/.netrc                           # ftp/curl credentials
~/.pgpass                          # Postgres password file
~/.npmrc                           # NPM registry auth
~/.pypirc                          # PyPI credentials
~/.git-credentials                 # HTTP git auth
/etc/sudoers                       # Linux-POSIX
/etc/passwd                        # Linux-POSIX
/etc/shadow                        # Linux-POSIX (root-readable, never write)
```

## Sensitive Directory Prefixes (H15)

```python
# src/eaccode/file_safety.py:build_write_denied_prefixes
~/.ssh/
~/.aws/                            # AWS credentials
~/.gnupg/                          # GPG keys
~/.kube/                           # Kubernetes config
/etc/sudoers.d                     # sudoers fragments
/etc/systemd                       # systemd units
~/.docker/
~/.azure/                          # Azure CLI
~/.config/gh/                      # GitHub CLI auth
~/.config/gcloud/                  # gcloud auth
```

## EACCODE_WRITE_SAFE_ROOT (H16, env-var)

Colon-separated (POSIX) / semicolon-separated (Windows) list of paths
allowed despite sensitive parents.

```
EACCODE_WRITE_SAFE_ROOT=/opt/data:/var/www html     # POSIX
EACCODE_WRITE_SAFE_ROOT=C:\data;D:\www             # Windows
```

Default: empty (no overrides).

## Tests

- `tests/test_file_safety.py` — 9 Tests
  - TestBuildPaths (ssh keys, dotenv)
  - TestPrefixes (aws, ssh, sudoers_d)
  - TestIsWriteDenied (blocks ssh, blocks aws, allows normal)
  - TestSafeRoots (whitelist works)

## Integration

`permissions.py:check()` calls `is_write_denied(path)` for mutating tools
(write_file, patch_file, etc.) AFTER the sensitive-path heuristic but
BEFORE the prompt. Result: writes to these paths are blocked outright,
no user prompt even in smart-mode/off-mode.

## Out-of-scope (Future)

- H17: classification categories (cross-profile, sandbox-mirror, container-mirror) — Hermes-specific
- H18: read-blocked subset (currently same as write-denied)
- H19: `raise_if_read_blocked` exception variant for code integration

## Reference

Hermes source: `_ref/hermes/agent/file_safety.py` (693 lines, Hermes-Verbatim patterns).

Plan: `.hermes/plans/2026-08-18_170452-hermes-safety-hardening.md`

## Code-Graph (generiert)

- `src/eaccode/file_safety.py` → [[15-features/system/config.md|config.yaml]]

