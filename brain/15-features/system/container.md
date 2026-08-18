---
name: container
type: system
status: done
phase: 08-18 plan-h-stufe-3
date: 2026-08-18
tags: [type/feature, feature/system, hermes, opt-in]
---

# Container-Sandbox-Backend (Plan H Stufe 3, opt-in)

> Real container isolation for tools that need a clean filesystem. Slim
> analog of Hermes' 3500-LOC container system.

## Was Stufe 3 macht

Wo Stufe 1 (cwd-as-workspace) per `Path.resolve` filtert und Stufe 2
(`/approvals allow-path`) explizite Freigaben erlaubt, packt Stufe 3 alles
in einen **echten Container** mit eigenem Image + Volume-Mounts. Opt-in via
`workspace.mode = "container"` — default bleibt soft-sandbox.

## Backends

| Mode | Was |
|---|---|
| `auto` | Docker wenn verfügbar, sonst fallback (soft-sandbox) |
| `docker` | Required Docker, raises wenn fehlt |
| `none` | Container-Layer komplett aus, nur soft-sandbox |

Default = `auto`.

## Public API

```python
@dataclass
class ContainerConfig:
    image: str = "python:3.11-slim"
    name: str = ""
    workspace: Path = Path.cwd()
    mounts: list[tuple[Path, str]] = []
    env: dict[str, str] = {}
    timeout_seconds: int = 300

# Container starten (returns Handle)
handle = start_container(ContainerConfig(image="python:3.11-slim"))

# In Container ausführen
exit_code, output = exec_in_container(handle, ["python", "--version"])

# Cleanup
stop_container(handle)
```

## Cleanup-Thread

`eaccode-*` Container mit laufendem Idle > 300 s werden vom Background-Thread
`_cleanup_inactive_containers()` (60 s tick) gestoppt. Pattern: `keep_set` =
Live-Handles, alles andere in `docker ps` ist stale.

## Safety: has_host_access_danger

Bevor Container gestartet wird, checkt `has_host_access_danger(mounts)`:
- Path startet mit `~/.ssh`, `~/.aws`, `~/.gnupg`, etc. → `True`
- Substring `.ssh`, `.aws`, `.gnupg`, `.kube`, `.docker` → `True`
- Prefix `~/` (User-Home) ODER `/etc`, `/var`, `/home` → `True`

Return `True` triggert im Caller eine hardline-prompt.

## Out-of-Scope (für Stufe 4+)

- Podman-Backend
- Container-in-Container (DinD)
- Image-Cache mit content-hash
- Multi-stage Builds
- Resource-Limits (cgroups v2)

## Tests

`tests/test_container.py` — Config-Instantiation, Docker-Pfad mit Mock,
Mount-Danger-Detection, Cleanup-Thread (mit fake `docker ps`).

## Verknüpft
[[15-features/system/workspace.md|workspace]] · [[15-features/system/path-security.md|path-security]]

Plan: `.hermes/plans/2026-08-18_203000-hermes-aufholjagd.md` (Stufe 3 Kapitel)
Hermes source: `_ref/hermes/terminal_tool.py` + `file_safety.py` + private `container_runner` (combined ~3500 LOC)

## Code-Graph (generiert)

- `src/eaccode/container.py` → —

