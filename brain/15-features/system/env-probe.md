---
name: env-probe
type: system
status: done
phase: 08-18 plan-g-v5-g6
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# Environment Probe (G.6)

> Erkennt einmalig, was im lokalen Env da ist (Python-Version, pip, PEP 668,
> git, npm, cargo, docker). Ergebnis landet im System-Prompt als Kontext.

## Erkannte Tools

- Python (`sys.executable --version`)
- pip / pipx (PEP-668-Marker)
- git (`git --version`)
- npm (`npm --version`)
- cargo (`cargo --version`)
- docker (`docker info`)
- node / bun (sofern vorhanden)

## Cache

```python
_GEN = 0
_CACHE: dict[str, str | None] = {}
_LOCK = threading.Lock()
```

Threadsafe, einmal pro Prozess. Tests rufen `force_reprobe()` auf, um nach
Subprocess-Mocks neu zu scannen.

## API

```python
def get_environment_probe_line() -> str
    # Liest Cache, returnt single-line summary (z. B. "Python 3.12.4 / pip 24.0 / git 2.46 / npm 10.x / docker not found")
def force_reprobe() -> None
def _probe_python_version() -> str | None
def _probe_command(name) -> str | None
```

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.6
- Hermes source: `_ref/hermes/tools/env_probe.py:get_environment_probe_line`

## Tests

`tests/test_env_probe.py` — Cache, force_reprobe, mock-subprocess pro Tool.
