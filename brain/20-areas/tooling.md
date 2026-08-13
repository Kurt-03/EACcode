---
date: 2026-08-13
status: active
area: tooling
tags: [area/tooling, type/area]
---

# Tooling & Repo-Konventionen *(timeless)*

## Stack

| Bereich | Wahl | Begründung |
|---|---|---|
| Sprache | Python 3.12+ | Hermes-ähnlich, Ökosystem, Cross-Platform |
| Dependencies | uv | schnell, reproduzierbar, `uv tool` für Installation |
| LLM | LiteLLM | BYOK: alle Provider über eine API |
| TUI | Textual | reichhaltig, Claude-Code-Niveau erreichbar |
| Memory | SQLite + FTS5 (B3) + Markdown | FTS5-Suche über Sessions |
| Cron | APScheduler + Daemon (C2) | Scheduling ohne Cloud |
| Interop | MCP-Protokoll (C3) | kein Vendor-Lock |
| Browser | Playwright (D6) | Automatisierung + Screenshots |
| Config | YAML + .env | Keys nie im Repo |
| Packaging | PyInstaller / `uv tool` (C5) | Win/Linux/macOS |

## Repo-Konventionen

- `src/eaccode/` (Package) · `tests/` · `docs/` · `brain/` (dieses Vault)
- Commits nur bei grünen Tests; Conventional Commits (`feat:`, `fix:`, `docs:`)
- LoC: 200–400/Datei, Hard Cap 600 — wachsende Dateien sofort aufteilen
- Tests: `uv run pytest` · Lint: `uv run ruff check .`

## Umgebungs-Fallen (Windows)

- `PYTHONPATH` aus der Hermes-Desktop-Umgebung vor Python-Aufrufen leeren
  (`export PYTHONPATH=`) — sonst bricht das Projekt-venv (pydantic_core-Fehler)
- `platformdirs` verdoppelt den App-Namen auf Windows → Pfade manuell
  (siehe [[adr/0001-config-yaml-design.md|ADR 0001]])
- git-bash: `cmd | tail` maskiert Exit-Codes → `set -o pipefail` + `PIPESTATUS`
