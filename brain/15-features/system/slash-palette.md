---
name: slash-palette
type: system
status: done
phase: D0.1+ (Nutzerwunsch 2026-08-13)
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Slash-Palette (Variante 3 — „Hermes-Flat")

## Zweck
`/` öffnet ein **randloses Overlay** mit allen Commands und Skills (fuzzy
gefiltert), Pfeiltasten navigieren, Enter wählt, Esc schließt — wie bei
Hermes / Claude Code.

## Implementierung
- `src/eaccode/palette.py` — eigene prompt_toolkit-Application:
  `PalettePrompt` (Buffer + Float-Layer), **eigenes Rendering**:
  ❯-Marker, aktive Zeile blau (statt Grau), Commands/Skills-Sektionen mit
  Trennlinie, Subsequence-Fuzzy, `eager`-Key-Bindings (↑/↓/Enter/Esc)
- `repl.py` — `_input_lines()`: TTY → Palette, sonst stdin (Tests/Pipes)
- `HELP_TEXT` in `commands.py`; Dependency: `prompt_toolkit>=3`

## Verifiziert (live, 2026-08-13, PTY)
- `/` → Overlay erscheint; `/mem` → Filter zeigt nur `/memory`
- Enter → `/memory` übernommen UND ausgeführt (Usage-Ausgabe)
- Pipe-Test: `/mem`+Enter → `/memory` (Application-Loop mit DummyOutput)

## Tests
`tests/test_palette.py` (10: Fuzzy, Entries, Refresh/Filter/Move/Accept,
Render-Sektionen, Pipe-Integration)

## Offene Punkte
- Kein Scrollbar bei sehr langen Listen (Float-Höhe folgt Inhalt)
- Rückbau möglich (Nutzer-Vorbehalt): Palette in palette.py isoliert

## Varianten-Historie (Entscheidungs-Log)
- **V1 „CC-Lean"** — prompt_toolkit-Styling (nicht gebaut, Option)
- **V2 „CC-Box"** — eigenes Overlay mit Rahmen (nicht gebaut, Option)
- **V3 „Hermes-Flat"** ✅ — randloses Overlay, ❯, Sektionen, blaues
  Highlight (gebaut, live, im REPL)
- **VA „TUI-CC-Layout"** — Vollbild-TUI als Auto-Start (getestet, 420 Tests,
  dann auf Nutzerwunsch REVERTIERT 08-14: REPL+Palette wieder Standard;
  TUI bleibt Skeleton) — Nutzerwunsch: Link-UX (Session-Links) fehlt,
  Vollbild nicht gewünscht

## REPL-Vollbild („Chat unten" — Nutzerwunsch, 2026-08-14)
- **`ChatApp`** in palette.py: prompt_toolkit-Vollbild — Log oben
  (Auto-Scroll, Scrollbar), Palette angepinnt über der Eingabe,
  Eingabe FEST unten mit ❯-Marker — Hermes-Look (kein Textual!)

## Feinschliff (2026-08-13, Nutzer-Wunsch)
- **Input-Prompt „❯ " jetzt blau** (`chat.prompt` = bold #4fc1ff, vorher
  Standard-Grau); steht als eigenes Window LINKS vom Buffer → immer vor
  dem Cursor
- **Chat-Log bricht nicht mehr am Rand um** (`wrap_lines=False`) —
  lange Zeilen laufen über den Rand statt zu wrappen
- **Test-Härtung**: 2 flaky Pipe-Tests warten jetzt auf `app.is_running`
  statt fixem sleep; 2 _ask-Tests testen den echten Inline-Flow (ask im
  Thread, Antwort via _submit) statt Event-Race — die Suite hängte sonst
  600s (Event wird in `_ask` ge-cleart)
- `run_repl`: TTY → ChatApp; Pipes/Tests → Stream-Loop (unverändert)
- Inline-Permission: `Allow: ... [y/N]` im Log, Antwort im Input-Feld
- Alle Slash-Commands, Store-Persistenz, Live-Filter beim Tippen,
  Enter: 1× Palette öffnen (Text bleibt), 2× übernehmen+ausführen
- Live verifiziert (PTY): `/version` → Palette → Enter → `eaccode 0.0.1`

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/skill-system.md|skill-system]] · [[15-features/system/repl.md|REPL]]

## Code-Graph (generiert)

- `src/eaccode/palette.py` → [[15-features/system/start-banner.md|start-banner]] · [[15-features/commands/README.md|README]] · [[15-features/system/config.md|config.yaml]] · [[15-features/system/skill-system.md|skill-system]] · [[15-features/system/session-store.md|session-store]] · [[15-features/system/tools-layer.md|tools-layer]]

