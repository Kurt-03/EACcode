---
name: container
type: system
status: done
phase: 08-18 plan-h-stufe-3
date: 2026-08-18
tags: [type/feature, feature/system, hermes, sandbox, docker]
---

# Container Sandbox (Stufe 3)

> Docker-Container-Per-Task mit Host-Path-Detection und Cleanup-Thread.

## Hermes-Verbatim Coverage

- `start_container(config)` — docker run mit Workspace-Mount
- `exec_in_container(handle, cmd)` — docker exec
- `stop_container(handle)` — docker stop
- `_cleanup_inactive_containers(handles)` — Cleanup-Thread analog
- `has_host_access_danger(mounts)` — Host-Path-Detection
- `list_running_containers()` — Docker ps wrapper

## Backends

- `BACKEND_AUTO` (default) — Docker wenn verfügbar
- `BACKEND_DOCKER` — Docker erforderlich
- `BACKEND_NONE` — Container-Layer off

## Defaults

- Image: `python:3.11-slim`
- Timeout: 300s
- Container-Name: `eaccode-<timestamp>`

## Host-Access-Detection

Dangerous mounts (blockiert):
- `~/.ssh`, `~/.aws`, `~/.gnupg`, `~/.kube`, `~/.docker`
- `/etc`, `/var`, `/root`, `/home`

## Cleanup

Cleanup-Thread check alle 60s nach inaktiven Containern und stoppt sie nach 5min idle.

## Reference

- Code: `src/eaccode/container.py`
- Tests: `tests/test_container.py`