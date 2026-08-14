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

## Variante 3 → Variante A (TUI, CC-Layout) — 2026-08-13
- Nutzer-Feedback: Overlay soll nicht mittig schweben, Eingabe unten fixiert
- **TUI als Standard bei TTY-Start** (`eaccode` im Terminal → Vollbild):
  Chat oben (Scroll), **PaletteOverlay angepinnt ÜBER der Input-Zeile**
  (kein Float!), Input `dock: bottom`
- TUI beherrscht jetzt ALLE Slash-Commands (parse_args aus commands.py),
  Markup-Escape für Agent-Text, Store-Persistenz wie REPL
- Stream-REPL bleibt für Pipes/Skripte; `eaccode tui` explizit weiter möglich

## Tests
`tests/test_palette.py` (10: Fuzzy, Entries, Refresh/Filter/Move/Accept,
Render-Sektionen, Pipe-Integration)

## Offene Punkte
- Kein Scrollbar bei sehr langen Listen (Float-Höhe folgt Inhalt)
- Rückbau möglich (Nutzer-Vorbehalt): Palette in palette.py isoliert

## Verknüpft
[[15-features/commands/README.md|README]] · [[15-features/system/skill-system.md|skill-system]] · [[15-features/system/repl.md|REPL]]

## Code-Graph (generiert)

- `src/eaccode/palette.py` → [[15-features/commands/README.md|README]] · [[15-features/system/skill-system.md|skill-system]]

