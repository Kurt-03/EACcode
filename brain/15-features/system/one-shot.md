---
name: one-shot
type: system
status: done
phase: A7
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: One-Shot (`-p`)

## Zweck
Ein Prompt, eine Antwort, Ende — für Skripte, Cron (Phase C) und Tests.

## Implementierung
- `src/eaccode/cli.py` — `_run_once(prompt, stdout)` → `eaccode -p "<prompt>"`
- Fehler → `Error: …` auf stdout, Exit 1 (kein Traceback)

## Beispiele
```
eaccode -p "Antworte nur mit: Hallo"
eaccode -p "Erstelle test.txt mit Inhalt 'hi'"    # nutzt Tools
```

## Tests
`tests/test_cli.py` — One-Shot-Fehlerpfad ohne Config

## Verknüpft
[[../README|Feature-Register]] · [[repl|REPL]]
