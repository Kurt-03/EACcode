---
date: 2026-08-13
status: accepted
phase: A2
tags: [type/adr]
---

# 0001 — config.yaml + Secrets-Design

## Kontext

eaccode braucht eine zentrale Konfiguration (Modelle, Provider, Pfade) mit
sicherem Umgang für API-Keys: BYOK (Keys gehören dem User), plattformkorrekte
Ablage (Windows/Linux/macOS), bedienbar aus CLI **und** REPL, nie Secrets im
Klartext ausgeben.

## Entscheidung

- **Eine `config.yaml`** mit fester Struktur (`model`, `providers`, `paths`),
  unter `%LOCALAPPDATA%\eaccode\` (Windows) bzw. `~/.config/eaccode/` (Unix) —
  **manuell gebaute Pfade statt `platformdirs`** (verdoppelt den App-Namen).
- **Secrets in der config.yaml** unter `providers.<name>.api_key` mit
  `chmod 600`; alternativ `.env` via `api_key_env` (env gewinnt).
- **`config show` maskiert Secrets** und zeigt pro Provider nur
  `set (file)` / `set (env: VAR)` / `not set`; `config get` verweigert Secrets.
- **Ein Befehlssatz für beide Flächen:** `config init/path/show/get/set/set-key/unset`
  als CLI und als `/config …` — gemeinsame Implementierung in `commands.py`.
- **`providers.*` ist dynamisch** (Sektionen entstehen beim Setzen);
  `model`/`paths` bleiben strikt (Typos → Fehler).

## Konsequenzen

- Provider/Modell-Verwaltung kam als dedizierte Kommandos (A3):
  `provider add/list/remove/set-key`, `model add/list/set-default/set-fallback/ping`.
- Key-Eingabe nur über verdeckten Prompt (`set-key`, getpass) — nie als
  CLI-Argument (Shell-History!).
- Altlasten des Vorgänger-Projekts im selben Ordner wurden entfernt
  (Backup: `%LOCALAPPDATA%\eaccode-old`).

## Alternativen (verworfen)

- `platformdirs` — verdoppelt App-Namen auf Windows → manuelle Pfade.
- Keys nur in `.env` — ok als Option, aber `set-key` ist bequemer und
  gleichermaßen geschützt.
