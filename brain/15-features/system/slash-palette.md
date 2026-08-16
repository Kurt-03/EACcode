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

## Feinschliff (2026-08-13/14, Nutzer-Wünsche)
- **Input-Prompt „❯ " jetzt blau** (`chat.prompt` = bold #4fc1ff); als
  `BeforeInput`-Processor im SELBEN Window wie der Buffer → **eine Zeile,
  links vom Cursor** (vorher separates Window darüber)
- **Agent-Antworten weiß** (`chat.agent` = bold white, vorher grün);
  **keine Symbole** mehr (⚡/⚕ entfernt — nur noch Text)
- **Keine Scrollbar-Margin** mehr (`right_margins=[]`); **Umbruch am
  Rand wieder AN** (`wrap_lines=True`, Nutzer-Entscheid 08-14)
- **Slash-Palette umgestellt** (08-14): flache Liste ohne Sections,
  Name links + Beschreibung rechts, sauber ausgerichtet (Hermes-Stil);
  ❯-Marker vor dem ausgewählten Eintrag; dynamische Spaltenbreite nach
  dem längsten Namen
- **Palette-Position** (08-14, Nutzer): erscheint **UNTER der
  Eingabezeile** (nicht darüber) — HSplit-Reihenfolge Log → Input →
  Palette; Höhe dynamisch 0–12 Zeilen (`Dimension(max=12)`,
  `dont_extend_height=True`); unsichtbar wenn zu (render leer)
- **Stream-Bereinigung** (08-14): Think-Blöcke (`<think>...</think>`)
  werden chunk-übergreifend gefiltert (MiniMax sendet Reasoning),
  `
` + ANSI-Escapes aus dem Stream entfernt — Antwort immer sichtbar
  (live: „Hallo Welt" statt `</think>`); Backspace/Delete löschen auch
  bei offener Palette, kein Bell bei leerem Buffer
- **Start-Banner** als erste Log-Zeilen (Style `chat.banner`, grau) +
  **Stat-Zeile** nach Antworten (Style `chat.stat`, gedimmt) — Details in
  [[15-features/system/start-banner.md|start-banner]]
- **Streaming (2026-08-14):** Agent-Antworten werden live in den Log
  gestreamt (Zeile wächst mit jedem Chunk, `app.invalidate()` aus dem
  Worker-Thread). Jede Agent-Runde bekommt einen Leer-Marker (neue
  Zeile); Tool-Calls erscheinen erst NACH dem vollständigen Stream der
  Runde (Loop-Reihenfolge: Stream zu Ende → Tool-Call → Permission).
  Router: `stream_completion` (stream=True) + `_completion_kwargs`;
  Agent: `run(on_token=...)` — siehe auch
  [[15-features/system/agent-core.md|Agent Core]]
- **Scrollback-Umbau (2026-08-14, Hermes-Parität):** Die ChatApp ist
  kein Vollbild mehr — `full_screen=False` (wie Hermes): Der gesamte
  Verlauf (Banner, Nachrichten, Antworten, Stat-Zeilen) läuft in den
  **nativen Terminal-Scrollback** (`_stream_out` → stdout + flush +
  `app.invalidate()` für Chrome-Redraw). prompt_toolkit verwaltet nur
  die untere Chrome (Eingabe + Palette). **Scrollen übernimmt das
  Terminal selbst** (CMD/Windows-Terminal-Scrollbar, Maus-Selektion,
  Terminal-Suche). `erase_when_done=True` räumt die Chrome beim Beenden
  ab. Grund: Nutzer-Feedback — der Chat lief „unsichtbar unter der
  Eingabe weiter", kein Scroll möglich; Hermes-Referenz: cli.py
  `full_screen=False` + patch_stdout-Transcript
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

