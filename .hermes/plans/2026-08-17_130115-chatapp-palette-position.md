# ChatApp — Palette-Position, Layout-Bug, Trenner & User-Echo — Plan

> **Status:** `DRAFT` — wartet auf User-Freigabe. Nicht ausführen.
> Eingefrorenes Design (8 Diskussions-Runden, 2026-08-17).

**Goal:** Die `ChatApp` in `src/eaccode/palette.py` zeigt einen sauberen, ruhigen, scanbaren Chat-Verlauf mit Palette **unter** `❯`, einem `●`-User-Echo, 1-LZ-Turn-Trennern und einer gestrichelten Linie **vor** `❯`. Drei sichtbare Bugs in einem Rutsch weg.

**Architecture:** Drei Patches, alle in `src/eaccode/palette.py`:
1. **`_push_input_to_bottom` entschärfen** — der `print("\n" * term_lines)`-Hack verursacht 30+ leere Zeilen; ersatzlos raus.
2. **`ChatApp.build_application` umbauen** — `HSplit` mit `Window(height=0)` durch `FloatContainer(content=HSplit([input_row]), floats=[palette_float])` ersetzen, mit `Float(ycursor=True)` wie in `PalettePrompt.build_application` (Z. 180-200).
3. **`_emit` + neue Hilfsmethoden** — `_divider()` (gestrichelte Linie), `_emit_turn()` (Turn-Trenner), `●`-Prefix vor User-Echo.

**Tech Stack:** Python 3.12+, `prompt_toolkit` (bereits in `pyproject.toml`), keine neuen Deps.

---

## 1. Was ist kaputt (drei sichtbare Bugs)

### Bug 1 — 30+ leere Zeilen vor `❯`

**Datei:** `src/eaccode/palette.py`, `ChatApp._push_input_to_bottom` (Z. 287-303).

**Aktueller Code:**
```python
def _push_input_to_bottom(self) -> None:
    try:
        term_lines = shutil.get_terminal_size().lines
        if term_lines > 2:
            print("\n" * (term_lines - 1), end="", flush=True)
    except Exception:
        pass
    try:
        if self._app is not None:
            self._app.invalidate()
    except Exception:
        pass
```

**Wirkung:** Druckt `term_lines - 1` Leerzeilen in den Scrollback (bei 50-Zeilen-Terminal = 49 Zeilen). Bei 30-Zeilen-Terminal = 29 Zeilen. Sichtbar im Attachment `abstand zu oben.md` (User-Snapshot): 35 leere Zeilen zwischen Tip und `❯`. Root-Cause: `full_screen=False` braucht diesen Hack nicht — prompt_toolkit hängt die Float-Chrome eh ans untere Terminal-Ende.

### Bug 2 — Slash-Palette sitzt über dem `❯`

**Datei:** `src/eaccode/palette.py`, `ChatApp.build_application` (Z. 575-581).

**Aktueller Code:**
```python
root = HSplit(
    [
        Window(height=0),  # filler: push chrome to the bottom
        input_row,
        palette_win,
    ]
)
```

**Wirkung:** `Window(height=0)` als Filler funktioniert nur in `full_screen=True`. Bei `full_screen=False` (Z. 588) hat der Filler genau 0 Zeilen, die anderen Elemente rutschen nicht nach unten. Palette erscheint **zwischen** Statusline und `❯`, drüber statt drunter.

### Bug 3 — kein `●` User-Echo, keine Turn-Trenner

**Datei:** `src/eaccode/palette.py`, `ChatApp._submit` (Z. 435-460) + `ChatApp._agent_worker` (Z. 364-407).

**Aktuell:** User-Echo ist nur eine blaue Zeile (`self._emit(text)`, Z. 455). Agent-Antwort und User-Echo haben keinen visuellen Unterschied (außer Farbe). Zwischen Turns gibt es keinen Abstand. Vor `❯` gibt es keinen Trenner.

---

## 2. Soll-Bild (e eingefrorenes, finales Design)

### 2.1 Visuell — Frischer Start

```
███████╗ █████╗  ██████╗ ██████╗  ██████╗ ██████╗ ███████╗
██╔════╝██╔══██╗██╔════╝██╔════╝ ██╔═══██╗██╔═══██╗██╔════╝
█████╗  ███████║██║     ██║      ██║   ██║██║   ██║█████╗
██╔══╝  ██╔══██║██║     ██║      ██║   ██║██║   ██║██╔══╝
███████╗██║  ██║╚██████╗╚██████╗ ╚██████╔╝╚██████╔╝███████╗
╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝

╭─ eaccode 0.0.1 · MiniMax-M3 (minimax) · C:\Users\kurtj ──────╮
│  Session: 20260817_163019_8e88a7                            │
│  Available Tools: 30                                        │
│  MCP Servers: Roblox_Studio (stdio)                         │
│  Available Skills: 1                                        │
│                                                            │
│  30 tools · 1 skills · /help for commands                  │
╰────────────────────────────────────────────────────────────╯

Welcome to eaccode! Type your message or /help for commands.
✦ Tip: /memory stores durable facts - eaccode remembers them across sessions.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
❯ ▌
```

### 2.2 Visuell — Mehrere Turns + Palette offen

```
●●● (Banner + Welcome + Tip + Linie wie oben) ●●●

● hi
Hi! How can I help you today?
MiniMax-M3 │ 22.6s │ 169 chars

● was kannst du?
I can help with coding, file editing, git, tests, memory, skills,
browser use, and more. I run in your terminal and remember
context across sessions.
MiniMax-M3 │ 4.3s │ 412 chars

● /version
eaccode 0.0.1

● rm -rf node_modules && npm install
Allow: run_command {"command": "rm -rf node_modules && npm install"} [y/N]
y
Command ran successfully. Reinstalled 1247 packages.
MiniMax-M3 │ 12.1s │ 87 chars

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
❯ /m█                                                                                                                              ← Cursor
                                                                                                                                    ← 1 LZ
  ❯ /model           modelle verwalten
    /memory          memory verwalten
    /skill           skills verwalten
    /job             jobs verwalten
  ❯ /zeit-helfer*    skill (uhrzeit)                                    ← Skill mit *
```

### 2.3 Style-Definitionen (final)

| Element | Style | Wert | Wirkung |
|---|---|---|---|
| `❯` (Prompt) | `chat.prompt` | `bold #4fc1ff` (hellblau) | Eingabe-Bereich, "von dir" |
| `●` + User-Text | `chat.user` | `bold #4fc1ff` (hellblau) | User-Echo, gleiche Farbe wie Prompt |
| Agent-Text | `chat.agent` | `bold white` | Antwort, neutral, fett |
| Statusline | `chat.stat` | `fg:#6e6e6e` (dunkelgrau) | Metadaten, gedimmt |
| Banner-Box | `chat.banner` | `fg:#9a9a9a` (mittelgrau) | Box + Welcome + Tip |
| **Linie vor ❯ (neu)** | `chat.divider` | `fg:#5a5a5a` (sehr dunkelgrau) | Struktur, fast unsichtbar |
| `Allow: …` | `chat.permission` | `bold #ffd166` (gelb) | Aufmerksamkeit, kein Error |
| Error | `chat.error` | `bold #ff6b6b` (rot) | Probleme |

**Keine Box** um User-Echo oder Agent-Antwort — nackter Text mit Farben + `●`-Marker. Die Banner-`╭─╮│╰─╯` ist die **einzige** Ausnahme, weil sie zum Banner-Design gehört.

### 2.4 Spacer-Regel (final)

| Übergang | Spacer |
|---|---|
| Banner → Welcome/Tip | 0 LZ |
| Welcome → erster Turn (`●`) | 1 LZ |
| Statusline (Ende Agent-Turn) → nächster Turn (`●`) | 1 LZ |
| Statusline (Ende Agent-Turn) → `❯` | 1 LZ + gestrichelte Linie |
| `Allow: …` → User-Antwort (`y`) | 0 LZ (Permission wartet auf Antwort) |
| Slash-Command-Output (z.B. `Usage: …`) → `❯` | 1 LZ + gestrichelte Linie |

### 2.5 Trennlinien (final, genau EINE)

- **Position:** Einmal **vor** `❯`, vor jeder Eingabe
- **Gestrichelt:** `- - - - - - - - -` (3× Space zwischen jedem `-`)
- **Breite:** 60 Zeichen Standard, mit `shutil.get_terminal_size().columns` clamped (min 40, max 80)
- **Farbe:** `chat.divider` = `fg:#5a5a5a` (gedimmt, fast unsichtbar)
- **Padding:** 1 LZ vor der Linie, 0 LZ nach der Linie (Linie sitzt **direkt** vor ❯)

### 2.6 Palette (final)

- **Position:** UNTER `❯` (Float mit `ycursor=True`)
- **Randlos** (kein Rahmen, flache Liste)
- **Max 8 Zeilen** (1 selektiert + 7 normal)
- **Zeilenformat:** `❯ /name           beschreibung` (selektiert: blauer BG, weißer Text)
- **Spalten dynamisch** nach längstem Namen + 2
- **Idle-Beschreibung:** gedimmt grau
- **Selektierte Beschreibung:** leuchtender (CC-Stil)
- **Skills-Indikator:** `*` nach Name (z.B. `/zeit-helfer*`)
- **Kein Treffer:** `(no matches)` (kursiv, gedimmt grau)
- **Keine Sektionen** (Commands + Skills zusammen, alphabetisch)

### 2.7 Verhalten / Tasten

| Taste | Aktion |
|---|---|
| `↑` / `↓` (Palette offen) | ❯ wandert in Palette |
| `Enter` (Palette offen) | Auswahl übernehmen, Palette zu |
| `Enter` (Palette zu) | Eingabe an Agent oder Slash-Command |
| `Esc` (Palette offen) | Palette zu, Eingabe bleibt |
| `Esc` (Palette zu) | App beenden, `bye` |
| `Ctrl+C` | App beenden, `bye` |
| `Backspace` leerer Buffer | NoOp, kein Bell |
| `Cursor move ↑/↓` ohne Palette | NoOp (Input hat keine History) |

---

## 3. Schritt-für-Schritt

### Schritt 1 — `_push_input_to_bottom` entschärfen

**Datei:** `src/eaccode/palette.py`, `ChatApp._push_input_to_bottom` (Z. 287-303).

**Änderung:**
```python
def _push_input_to_bottom(self) -> None:
    """Redraw the chrome so it sits at the bottom of the terminal.

    With full_screen=False + Float (ycursor=True), prompt_toolkit already
    pins the chrome to the bottom — no need to spam newlines into the
    scrollback (that caused 30+ blank lines before the prompt).
    """
    try:
        if self._app is not None:
            self._app.invalidate()
    except Exception:
        pass
```

**Verifikation:** `uv run eaccode` zeigt 0 leere Zeilen zwischen Tip und `❯`.

### Schritt 2 — `_divider()` als neue Methode

**Datei:** `src/eaccode/palette.py`, neue Methode in `ChatApp` (nach `_push_input_to_bottom`).

**Code:**
```python
def _divider(self) -> str:
    """Return a dimmed dashed line for above the prompt."""
    try:
        width = shutil.get_terminal_size().columns
    except Exception:
        width = 60
    width = max(40, min(width - 4, 80))
    return "- - " * (width // 4)
```

**Plus neue Style-Klasse** in `ChatApp.STYLE` (Z. 246-263):
```python
"chat.divider": "fg:#5a5a5a",
```

### Schritt 3 — `_emit` patchen

**Datei:** `src/eaccode/palette.py`, `ChatApp._emit` (Z. 305-312).

**Code:**
```python
def _emit(self, text: str) -> None:
    """Print one line into the terminal scrollback.

    Called from the main or worker thread; when patch_stdout is active
    the write lands above the input chrome.
    Empty text means an explicit blank line (used as turn spacer).
    """
    with contextlib.suppress(Exception):
        if text:
            print(text)
        else:
            print()  # explicit blank line
```

### Schritt 4 — `●` User-Echo in `_submit`

**Datei:** `src/eaccode/palette.py`, `ChatApp._submit` (Z. 435-460).

**Code-Patch** (Z. 455):
```python
# alt:
self._emit(text)
# neu:
self._emit(f"● {text}")
```

(`●` ist U+25CF, "Black Circle", 1 Zeichen breit in Monospace.)

### Schritt 5 — Linie vor `❯` einbauen

**Datei:** `src/eaccode/palette.py`, `ChatApp.run` (Z. 611-626).

**Code-Patch:**
```python
def run(self) -> str:
    with contextlib.suppress(Exception):
        from eaccode import store as _store
        self._session_id = _store.new_session()

    self._print_banner()
    self._push_input_to_bottom()
    self._wire_permission()
    # NEU: einmal vor jeder Eingabe die Trennlinie drucken
    self._emit(self._divider())
    app = self.build_application()
    from prompt_toolkit.patch_stdout import patch_stdout
    with patch_stdout():
        return app.run()
```

**Begründung:** Die Linie wird **einmal** zu Beginn gedruckt und bleibt im Scrollback stehen. Wenn der User neue Turns startet, kommt sie wieder — siehe Schritt 6.

### Schritt 6 — Linie + LZ nach Turn-Ende

**Datei:** `src/eaccode/palette.py`, `ChatApp._agent_worker` (Z. 364-407).

Nach der `render_status_line`-Ausgabe (Z. 399-407) muss **1 LZ + Linie** kommen:

```python
try:
    from eaccode import config as cfg
    self._emit(
        render_status_line(
            model_label(cfg.load_config()),
            time.monotonic() - start,
            len(answer),
        )
    )
    self._emit("")  # NEU: 1 LZ Abstand zur Linie
    self._emit(self._divider())  # NEU: Trennlinie vor nächstem ❯
except Exception:
    pass
```

**Plus:** Bei Slash-Command-Output (`_run_slash`, Z. 462-496) ebenfalls Linie am Ende:

```python
self._emit(output.getvalue().rstrip())
self._emit("")  # NEU
self._emit(self._divider())  # NEU
```

**Achtung — keine Linie/kein LZ vor `Allow: …`** (Permission wartet auf Antwort, sonst wirkt's zögerlich). Im `_ask` (Z. 411-416) bleibt alles unverändert.

### Schritt 7 — Layout-Umbau: Float statt HSplit

**Datei:** `src/eaccode/palette.py`, `ChatApp.build_application` (Z. 511-591).

**Code-Patch:**
```python
# alt (Z. 570-581):
palette_win = Window(
    self._palette_control(),
    height=Dimension(max=12),
    dont_extend_height=True,
)
root = HSplit(
    [
        Window(height=0),  # filler: push chrome to the bottom
        input_row,
        palette_win,
    ]
)

# neu:
from prompt_toolkit.layout import Float, FloatContainer
palette_float = Float(
    content=Window(
        self._palette_control(),
        height=Dimension(max=8),       # war: max=12, User-Wunsch: 8
        dont_extend_height=True,
    ),
    ycursor=True,                     # Float sitzt unter Cursor
    allow_cover_cursor=False,
)
root = FloatContainer(
    content=HSplit([input_row]),
    floats=[palette_float],
)
```

**Imports anpassen** (Z. 33-42): `Float`, `FloatContainer` müssen importiert werden.

Schau in `PalettePrompt.build_application` (Z. 180-200) — dort ist das Pattern bereits richtig umgesetzt. Analog übertragen.

### Schritt 8 — Tests

**Datei:** `tests/test_palette.py`, neue Tests:

```python
class TestChatAppLayout:
    def test_root_is_float_container(self) -> None:
        """ChatApp uses FloatContainer so the palette sits below the prompt."""
        from prompt_toolkit.layout import Float, FloatContainer
        app = ChatApp(agent_factory=lambda: None)
        app.build_application()
        assert isinstance(app._app.layout.container, FloatContainer)
        floats = app._app.layout.container.floats
        assert len(floats) == 1
        assert isinstance(floats[0], Float)

    def test_palette_float_uses_ycursor(self) -> None:
        """The palette float uses ycursor=True so it sits below the cursor."""
        app = ChatApp(agent_factory=lambda: None)
        app.build_application()
        float_obj = app._app.layout.container.floats[0]
        assert float_obj.ycursor is True

    def test_palette_max_height_is_8(self) -> None:
        """Palette max height is 8 rows (1 selected + 7 normal)."""
        app = ChatApp(agent_factory=lambda: None)
        app.build_application()
        window = app._app.layout.container.floats[0].content
        assert window.height.max <= 8


class TestChatAppDivider:
    def test_divider_is_dashed(self) -> None:
        """Divider contains '- - ' segments."""
        app = ChatApp(agent_factory=lambda: None)
        divider = app._divider()
        assert "- - " in divider
        assert len(divider) >= 40

    def test_divider_adapts_to_terminal_width(self, monkeypatch) -> None:
        """Divider width is clamped to terminal."""
        from unittest.mock import patch
        app = ChatApp(agent_factory=lambda: None)
        with patch("shutil.get_terminal_size", return_value=type("S", (), {"columns": 30})()):
            assert len(app._divider()) <= 30
        with patch("shutil.get_terminal_size", return_value=type("S", (), {"columns": 200})()):
            assert len(app._divider()) <= 80


class TestChatAppUserEcho:
    def test_user_echo_has_bullet(self, monkeypatch) -> None:
        """User messages are echoed with a '● ' prefix."""
        app = ChatApp(agent_factory=lambda: None)
        captured = []
        monkeypatch.setattr(app, "_emit", lambda t: captured.append(t))
        # simulate a chat submit (no slash, no permission pending)
        app._permission_prompt = None
        app.palette.visible = False
        # stub agent.run so we don't actually call the LLM
        class FakeAgent:
            def run(self, messages, on_token=None):
                return messages + [{"role": "assistant", "content": "ok"}]
            def last_text(self, history):
                return "ok"
        app._agent = FakeAgent()
        app._submit("hi")
        # First thing emitted is the user echo with bullet
        assert any(line.startswith("● ") for line in captured if line)
```

**Bestehende Tests** bleiben unverändert. Besonders:
- `test_palette_filter_and_accept` (Filter + Selected)
- `test_chatapp_*` (Submission, Slash, History)
- `test_palette_pipe_integration` (DummyOutput)

Diese könnten Anpassung brauchen, wenn sie Layout-Details prüfen — wird beim Ausführen geprüft.

### Schritt 9 — Brain & Doku

**Dockerfile/Gehirn:**
- `brain/15-features/system/slash-palette.md` — Section "Palette-Position" erweitern mit "Float + ycursor=True Pattern" + Verweis auf Bug 1 (Layout) und Bug 2 (Spacer-Hack)
- `brain/15-features/system/start-banner.md` — Section "Stat-Zeile" erweitern mit "1 LZ + gestrichelte Linie vor ❯"
- `brain/15-features/system/repl.md` — Offene-Punkte-Section updaten, falls der Plan was altes aufhebt

**Manual-Test:**
- `docs/manual-test.md` — neuer Test-Block: "ChatApp: Layout, Palette-Position, Trenner"

**Neuer Eintrag in `brain/15-features/system/turn-marker.md`** (optional, falls dir das lieber ist) — dokumentiert die `●`-Echo-Konvention.

### Schritt 10 — Live-Verifikation

Terminal-Breite ≥ 80, in CMD oder Windows-Terminal:

```bash
export PYTHONPATH=  # Hermes-venv-Falle
uv run eaccode
```

**Erwartungen:**
1. Banner erscheint 1×, **0 leere Zeilen** vor `❯`
2. `hi` tippen + Enter → `● hi` (blau fett), dann Antwort weiß fett, Statusline gedimmt
3. Linie `─ ─ ─` vor nächstem `❯` sichtbar
4. `/` tippen → Palette erscheint **direkt unter** `❯`, nicht über
5. `/ver` tippen → 1 Treffer `/version`, blaue Zeile
6. Enter → Palette zu, `/version` im Buffer
7. Enter nochmal → `eaccode 0.0.1` ausgegeben, Linie vor ❯
8. `rm -rf /test` + Enter → `Allow: run_command … [y/N]` ohne LZ, direkt darunter
9. `y` tippen → Antwort, Statusline, Linie, ❯
10. Ctrl+C → `bye`, Exit 0

Vergleich vorher/nachher: gleichen Output in Screenshot, aber Vorher mit 35 LZ und Palette über ❯, Nachher 0 LZ und Palette unter ❯.

### Schritt 11 — Commits

Drei Commits, jeder isoliert und rollback-fähig:

```bash
git add src/eaccode/palette.py tests/test_palette.py
git commit -m "fix(chat): remove newline-spam in _push_input_to_bottom — 0 LZ before ❯"

git add src/eaccode/palette.py tests/test_palette.py
git commit -m "fix(chat): ChatApp palette as Float (ycursor=True) below ❯"

git add src/eaccode/palette.py tests/test_palette.py brain/15-features/system/slash-palette.md brain/15-features/system/start-banner.md docs/manual-test.md
git commit -m "feat(chat): user echo '● ', dashed divider before ❯, palette to 8 rows"
```

---

## 4. Dateien, die sich ändern

| Datei | Art | Zweck |
|---|---|---|
| `src/eaccode/palette.py` | Modify | Alle drei Patches (Schritte 1, 3-7) |
| `tests/test_palette.py` | Modify | Neue Tests (Schritt 8) |
| `brain/15-features/system/slash-palette.md` | Modify | Doku float-pattern + entschärfter Spacer-Hack |
| `brain/15-features/system/start-banner.md` | Modify | Linie-vor-❯ dokumentieren |
| `brain/15-features/system/repl.md` | Modify | Offene-Punkte-Section |
| `docs/manual-test.md` | Modify | Test-Anleitung |

**Nicht ändern:**
- `src/eaccode/banner.py` — Block-Art bleibt
- `src/eaccode/repl.py` — Stream-Loop bleibt unverändert
- `src/eaccode/cli.py` — kein Touch
- `src/eaccode/palette.py` `PalettePrompt` (Z. 92-232) — nutzt schon Float, Vorbild für unseren Patch

---

## 5. Tests / Validation

### 5.1 Unit

- `pytest tests/test_palette.py -v` — alle grün
- `pytest tests/test_repl.py -v` — Stream-REPL bleibt grün
- `pytest tests/test_banner.py -v` — Banner-Tests bleiben grün
- `pytest tests/test_cli.py -v` — CLI-Tests bleiben grün

### 5.2 Live-Verifikation (User-Test, Schritt 10)

Vor Freigabe **muss** der User selbst `uv run eaccode` starten und die 10 Erwartungen durchgehen.

**Bestätigung an mich:** Wenn alle 10 Schritte wie erwartet laufen, gib den Plan frei.

### 5.3 Regressions-Risiken

- **Pipe-Tests** (`test_palette_pipe_integration`): `Float` braucht Terminfo. Im `DummyOutput`-Pfad rendert `Float` ohne echte Cursor-Koordinaten — aber `full_screen=False` + `Float` ist ein unterstützter prompt_toolkit-Pfad (siehe `PalettePrompt`-Tests).
- **`erase_when_done=True`** (Z. 589): Float muss beim Beenden mit gelöscht werden. Standard, aber kurz manuell verifizieren.
- **`patch_stdout`** (Z. 625-626): Float und patch_stdout interagieren normalerweise sauber — Float lebt im Application-Layout, patch_stdout betrifft nur externes `print()`. Beim ersten Live-Test beobachten.
- **`_emit("")` für LZ-Spacer:** bei Stream-Chunks darf das nicht zwischen einzelnen Tokens passieren. Wir printen `_emit("")` nur **am Ende** einer Runde (nach Statusline), nicht pro Stream-Chunk. Code-Patch in Schritt 6 berücksichtigt das.

---

## 6. Finalität der Design-Entscheidungen

Alle Punkte aus 8 Diskussions-Runden, eingefroren am 2026-08-17:

| # | Aspekt | Entscheidung |
|---|---|---|
| 1 | Palette-Position | UNTER ❯ (Hermes-Stil, Float mit `ycursor=True`) |
| 2 | Banner-Stil | Block-Art `███████╗` (klein, 6 Zeilen) |
| 3 | Banner-Häufigkeit | 1× |
| 4 | Palette-Ränder | **randlos** |
| 5 | Palette-Sektionen | keine |
| 6 | Palette-Spalten | dynamisch nach längstem Namen + 2 |
| 7 | Palette-Marker | ❯ vor selektiert, `  ` vor anderen |
| 8 | Skills-Indikator | `*` nach Name |
| 9 | Idle-Beschreibung | gedimmt grau |
| 10 | Selektierte Beschreibung | leuchtender (CC-Stil) |
| 11 | Palette-Höhe | max 8 Zeilen |
| 12 | Kein Treffer | `(no matches)` |
| 13 | Enter 1× in Palette | Auswahl übernehmen |
| 14 | Enter 2× | Kommando ausführen |
| 15 | ↑↓ in Palette | ❯-Navigation |
| 16 | ↑↓ außerhalb Palette | NoOp |
| 17 | Esc Palette offen | Palette zu |
| 18 | Esc Palette zu | beenden |
| 19 | Ctrl+C | beenden |
| 20 | Backspace leerer Buffer | NoOp, kein Bell |
| 21 | Spacer nach Output | 1 LZ |
| 22 | Spacer nach Banner | 0 LZ |
| 23 | Spacer nach Allow: | 0 LZ |
| 24 | User-Echo-Marker | `●` (blau fett) |
| 25 | Color User | `#4fc1ff` hellblau (gleich wie Prompt) |
| 26 | Color Agent | `bold white` |
| 27 | Trennlinien | 1× vor ❯, gestrichelt `- - -` |
| 28 | Trennlinien-Farbe | `fg:#5a5a5a` (fast unsichtbar) |
| 29 | Trennlinien-Breite | 60 (clamped 40-80) |
| 30 | Initial-LZ-Spam | RAUS (Bug) |

**Bei Abweichungen** vom Plan: User kann nach Implementierung jederzeit nachjustieren — diese Liste ist die Baseline.

---

## 7. Out-of-Scope (bewusst nicht drin)

- **Token-Stats / Progress-Bar** in Statusline (Hermes hat das, wir nicht)
- **Tools/Skills-Listing mit Namen** (nur Anzahl)
- **Update-Hinweis** für neue Versionen
- **Style-Konfigurierbarkeit** via `config.yaml`
- **Banner-FIGlet-Tausch** (du hast Block-Art bestätigt)
- **Volle Hermes-Statusline** (Token-Count, Progress, TTFB, Title)
- **TUI/Textual-Migration** (revertiert 08-14, kein Anfasser)

---

## 8. Aufwand & Reihenfolge

| # | Schritt | Dauer | Commit |
|---|---|---|---|
| 0 | Tests lesen, bestehende Suite verstehen | 3 min | — |
| 1 | `_push_input_to_bottom` Spacer-Hack raus | 3 min | `fix(chat): remove newline-spam` |
| 8a | Test `test_root_is_float_container` schreiben | 2 min | — |
| 7 | Float-Layout-Umbau | 8 min | `fix(chat): palette as Float` |
| 2 | `_divider()` + Style-Klasse | 4 min | — |
| 3 | `_emit` patchen | 2 min | — |
| 4 | `●` User-Echo | 2 min | — |
| 5 | Linie vor ❯ beim Start | 2 min | — |
| 6 | Linie + LZ nach Turns | 4 min | — |
| 8b | Restliche Tests | 4 min | — |
| 9 | Brain + manual-test.md | 5 min | — |
| 10 | Live-Verifikation (manuell) | 5 min | — |

Gesamt: ~42 min, 3 Commits, 1 großer Live-Test.

---

## 9. Status

**`DRAFT`** — wartet auf User-Freigabe.

Reihenfolge der Implementierung (Schritt 1 **zwingend zuerst**, weil ohne ihn alle weiteren Tests visuell durch den Spacer-Hack verdeckt werden):

1. Schritt 1 (Spacer-Hack raus) — sichtbar sofort
2. Schritt 7 (Float-Layout) — sichtbar bei `/`-Eingabe
3. Schritte 2-6 (Turn-Marker, Trenner, Echo) — sichtbar bei jedem Chat
4. Schritte 8-9 (Tests + Doku)
5. Schritt 10 (Live-Verifikation)
