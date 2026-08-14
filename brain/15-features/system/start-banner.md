---
name: start-banner
type: system
status: done
phase: D0.1
date: 2026-08-14
tags: [type/feature, feature/system]
---

# System: Start-Banner (Hermes-Stil)

## Zweck
Startbildschirm nach dem Hermes-Vorbild: ASCII-Logo + Status-Box +
Welcome/Tip + Stat-Zeile nach Antworten.

## Umfang
- `banner.py`: `render_banner(conf, session_id, cwd)` — Logo (EACCODE,
  Block-Art), Box mit abgerundeten Ecken (╭─╮│╰─╯), Inhalt: Version ·
  Modell (aus config, z. B. `MiniMax-M3 (minimax)`) · CWD · Session ·
  Tools-Zahl (30, live gezählt über alle Factories) · MCP-Server ·
  Skills-Zahl (nur wenn >0) · Footer „N tools · N skills · /help"
- `status_line(model, seconds, chars)`: `⚕ Modell │ 3.2s │ 412 chars`
- **Stream-REPL** (`eaccode` in echter CMD/Pipe-TTY): Banner statt
  Einzeiler — nur wenn `stdout.isatty()` und nicht `EACCODE_QUIET=1`
  (Hermes-`-Q`-Parität); sonst kompakter Einzeiler (Tests/Pipes bleiben
  stabil)
- **ChatApp** (Vollbild): Banner als erste Log-Zeilen (Style
  `chat.banner`, grau) mit Session-ID; nach jeder Agent-Antwort eine
  Stat-Zeile (Style `chat.stat`, gedimmt) mit Modell, Dauer, Zeichen —
  **ohne Symbole** (⚡/⚕ entfernt, Nutzer-Wunsch 08-14)
- **Box passt sich dem Inhalt an** (kein Fixed-Width): alle Wand-Zeilen
  exakt gleich breit — kein Clipping in schmalen Fenstern (Regressions-
  Test `TestBoxWalls`)

## Verifiziert
- Unit: 15 Banner-Tests (Logo, Box, Modell-Label, MCP, Skills, Quiet,
  Statuszeile)
- Live (2026-08-14): Render über TTY-Proxy exakt wie Vorbild; in echter
  CMD erscheint er automatisch (stdout = TTY)

## Design-Prinzip
Dynamische Felder (Modell, Tools, Skills, MCP) werden live aus Config
und Tool-Factories gezählt — kein Hardcode. Skills-Zeile entfällt bei 0.

## Code-Graph (generiert)

- `src/eaccode/banner.py` → [[15-features/system/diff-editing.md|diff-editing]] · [[15-features/system/git-pr.md|git-pr]] · [[15-features/system/learning-loop.md|learning-loop]] · [[15-features/system/memory.md|Memory]] · [[15-features/system/repo-understanding.md|repo-understanding]] · [[15-features/system/skill-system.md|skill-system]] · [[15-features/system/test-runner.md|test-runner]] · [[15-features/system/tools-layer.md|tools-layer]]

