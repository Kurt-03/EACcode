---
date: 2026-08-13
status: accepted
phase: A2
---

# 0001 — config.yaml + Secrets-Design

## Kontext

eaccode braucht eine zentrale Konfiguration (Modelle, Provider, Pfade) mit
sicherem Umgang für API-Keys. Anforderungen: BYOK (Keys gehören dem User),
plattformkorrekte Ablage (Windows/Linux/macOS), bedienbar aus CLI **und** REPL,
nie Secrets im Klartext ausgeben.

## Entscheidung

- **Eine `config.yaml`** mit fester Struktur (`model`, `providers`, `paths`),
  gespeichert unter `%LOCALAPPDATA%\eaccode\` (Windows) bzw.
  `~/.config/eaccode/` (Unix) — **manuell gebaute Pfade statt `platformdirs`**
  (die Bibliothek verdoppelt auf Windows den App-Namen, `appauthor=None`
  hilft nicht).
- **Secrets in der config.yaml** unter `providers.<name>.api_key` mit
  `chmod 600`; alternativ `.env`-Variablen via `api_key_env` (env gewinnt).
- **`config show` maskiert Secrets** (`sk-***`) und zeigt pro Provider nur
  `set (file)` / `set (env: VAR)` / `not set`; `config get` verweigert Secrets.
- **Ein Befehlssatz für beide Flächen:** `config init/path/show/get/set/set-key/unset`
  als CLI (`eaccode config …`) und als REPL-Slash-Command (`/config …`) —
  gemeinsame Implementierung in `commands.py`.
- **`providers.*` ist dynamisch** (fehlende Sektionen werden beim Setzen
  automatisch angelegt); `model`/`paths` bleiben strikt (Typos → Fehler).
- `.env` wird beim Start geladen (Config-Ordner + CWD).

## Konsequenzen

- Provider/Modell-Verwaltung kommt als dedizierte Kommandos in A3
  (`provider add`, `model list`, …) — die config.yaml bleibt reine Speicher-Ebene.
- Key-Eingabe nur über verdeckten Prompt (`config set-key`, getpass) —
  nie als CLI-Argument (sonst landet er in der Shell-History).
- Altlasten des Vorgänger-Projekts im selben Ordner wurden entfernt
  (Backup: `%LOCALAPPDATA%\eaccode-old`).

## Alternativen (verworfen)

- `platformdirs` — verdoppelt App-Namen auf Windows → manuelle Pfade.
- Keys nur in `.env` — ok als Option, aber `set-key`-Speicherung ist
  bequemer und gleichermaßen geschützt.
