# eaccode — Manueller Verifikations-Fahrplan

Wie du nach jedem Schritt selbst prüfst, dass eaccode wirklich funktioniert.
**Reihenfolge nach jedem Step:** ① pytest → ② ruff → ③ Live-Check (unten) → ④ Commit.

> Hinweis: Die Subkommando-Namen (`config set`, `model ping`, …) sind Zielvorgaben
> aus dem Master-Plan und können beim Bauen leicht variieren. Die *Erwartung* bleibt gleich.

---

## Allgemeine Regeln (gelten immer)

| Check | Kommando | Erwartung |
|---|---|---|
| Unit-Tests | `uv run pytest -q` | `N passed` (keine failures/errors) |
| Lint | `uv run ruff check .` | `All checks passed!` |
| Live-Check | echtes Kommando ausführen | Ausgabe entspricht Erwartung — Tests sind **kein** Beweis |
| Commit | erst wenn ①–③ grün | nie bei roten Tests committen |

---

## Phase A — Foundation & MVP ✅ (v0.0.1, Stand 2026-08-13)

> Alle Live-Checks laufen **in der eaccode-Session**: `eaccode` in der CMD starten,
> dann die Slash-Commands nutzen. Alternativ `eaccode <command>` direkt.

### A1–A8: Kompletter Session-Durchlauf

| Check | Kommando (in der Session) | Erwartung |
|---|---|---|
| Start | `eaccode` | Banner `eaccode 0.0.1 - self-improving generalist agent. Type /help` |
| Version | `/version` | `eaccode 0.0.1` |
| Hilfe | `/help` | Liste aller Befehle |
| Config | `/config show` | Werte sichtbar, **Keys maskiert** (`sk-***` / `not set`) |
| Provider | `/provider list` | Provider mit Key-Status + base_url |
| Modelle | `/model list` | Katalog mit `(default)` / `(fallback)`-Markern |
| Memory | `/memory add Test` · `/memory show` | `ok` · Eintrag in `## Agent Memory` |
| Chat | normalen Text senden | `eaccode> <Antwort>` (braucht API-Key) |
| One-Shot | `eaccode -p "Hallo"` | Antwort ODER sauberer `Error:` (kein Key) |
| TUI | `eaccode tui` | App startet, **Input-Fokus**, `/help` funktioniert, `Ctrl+Q` beendet |

### Key eintragen (einmalig, für echte Chat-Calls)

```
/provider set-key openrouter     ← verdeckte Eingabe, kein Echo
/model ping openrouter/anthropic/claude-sonnet-4   → "replied: pong"
```

### A5-Tools live testen (Chat-Nachrichten in der Session)

| Tool | Eingabe (als Chat) | Erwartung |
|---|---|---|
| current_time | `Wie spät ist es gerade?` | Antwort mit Uhrzeit |
| system_info | `Was für ein System bin ich?` | OS + Hardware |
| write_file | `Erstelle test.txt mit Inhalt "Hallo eaccode"` | `written …` |
| read_file | `Lies test.txt` | Inhalt |
| list_files | `Was liegt in <ordner>?` | Dateiliste |
| search_files | `Suche in <ordner> nach "<muster>"` | Pfade |
| run_command (erlauben) | `Führe echo hallo aus` | `Allow: … [y/N]` → `y` → `hallo` |
| run_command (verweigern) | `Führe dir /b aus` | `n` → `permission denied` |
| http_get | `Lade https://example.com und fasse zusammen` | Zusammenfassung |
| web_search | `Suche im Web: Wetter Berlin heute` | Titel + Links |

### Fallback-Chain testen

```
/model set-default minimax/gibt-es-nicht      ← kaputtes Default
Chat-Nachricht senden                          → fällt auf Fallback zurück ODER
                                                sauberer "all models failed"-Error
/model set-default minimax/MiniMax-M3          ← zurücksetzen
```

---

## Phase B — Hermes-Core

### B1/B2: Skills & Learning-Loop

| Check | Eingabe | Erwartung |
|---|---|---|
| Skill ansehen | `/skill list` | `zeit-helfer` + eigene Skills |
| Skill-Injection | `Wie spät ist es? UHRZEIT` | Antwort mit echter Zeit (Skill + current_time) |
| Learning-Loop | `Erstelle einen Skill namens begruessung mit Trigger hallo: Begrüße freundlich` | Agent ruft `create_skill` auf → `skill 'begruessung' created` |
| Skill wirkt | `Hallo!` | Begrüßung nach Skill |
| Dedup | `Erstelle nochmal einen Skill mit Trigger hallo` | `Error: trigger 'hallo' is already used` |
| Aufräumen | `/skill remove begruessung` | `skill 'begruessung' removed` |

### B3: Session-Store

| Check | Eingabe | Erwartung |
|---|---|---|
| Chat wird gespeichert | `Wie baue ich einen Router?` + `/session browse` | Session mit Titel + `2 msgs` |
| Volltextsuche | `/session search Router` | Session + Snippet (`(2 hits)`) |
| Session anzeigen | `/session show <id>` | `[user]` + `[assistant]` Zeilen |
| Agent-Suche | `Durchsuche deine alten Sessions nach Router und fasse zusammen` | Agent nutzt `session_search`, Antwort mit Fundstellen |
| @session:-Link | `Was war in dieser Session? @session:<id>` | Agent bekommt den Session-Inhalt als Kontext und fasst zusammen |
| Scroll (Agent) | `Schau in die letzte Session und sag mir die letzte Frage` | Agent nutzt `session_scroll` |

### B4: Memory-Hierarchie

| Check | Eingabe | Erwartung |
|---|---|---|
| Agent merkt selbst | `Merke dir: Ich trinke Kaffee` | Fakt landet in USER.md |
| Beweis | `/memory show` | `## About the User` + `- Trinkt Kaffee` |
| Überleben | `/exit` → `eaccode` → `Was trinke ich?` | erinnert sich (Memory-Injection) |
| Konsolidierung | viele Fakten hinzufügen (über 2200 Zeichen) | `Consolidate now`-Meldung, nichts wird blind angehängt |

### B5: Subagents

| Check | Eingabe | Erwartung |
|---|---|---|
| 2 parallel | `Starte ZWEI Subagenten parallel: A (nur http_get) holt https://example.com, B (nur http_get) holt https://example.org. Nenne beide Titel.` | beide Antworten in ~15–20 s (parallel), 403 von example.org sauber gemeldet |
| Reasoning-only | `Starte einen Subagenten ohne Tools, der ein Gedicht schreibt.` | Gedicht kommt |
| Unbekanntes Tool | `Starte einen Subagenten mit dem Tool ghost_tool.` | `Error: unknown tool: ghost_tool (available: …)` |
| Tool-Restriktion | `Starte einen Subagenten, der nur current_time darf, und frag nach der Zeit.` | nur die Zeit, keine Datei-/Web-Zugriffe |

### B6: Parallel-Execution

| Check | Eingabe | Erwartung |
|---|---|---|
| Echte Parallelität | 2 Subagents (oben) | Gesamtzeit ≈ ein Subagent (nicht doppelt) |
| Fehler-Isolation | Subagent A bekommt kaputte URL (403), B funktioniert | B liefert trotzdem, A meldet sauber, Haupt-Agent fasst beide zusammen |

### D6: Browser

| Check | Eingabe | Erwartung |
|---|---|---|
| Navigieren | `Öffne https://example.com` | Titel + URL zurück |
| Lesen | `Lies den Inhalt der Seite` | Text der Seite (browser_extract) |
| Screenshot | `Mache einen Screenshot nach C:\Users\...\browser-test.png` | PNG-Datei entsteht (einmalig: `playwright install chromium` nötig) |
| Session | `Öffne example.com, dann example.org` + `Wo bin ich gerade?` | Agent nutzt browser_status, URL bleibt erhalten |
| Fehlerpfad | `Öffne https://example.com/definitiv-nicht-da` | saubere Fehlermeldung, kein Crash |

Hinweis: Browser-Tools sind mutierend → Permission-Prompt `Allow: browser_navigate … [y/N]` → `y`.

---

## Phase C — Production-Reife

### C1 Permission-/Sandbox-System

| Check | Kommando | Erwartung |
|---|---|---|
| Ask-by-default | `uv run eaccode -p "Lösche test.txt"` | Permission-Prompt, ohne Bestätigung passiert nichts |
| Auto-Approve | `uv run eaccode --approve terminal -p "..."` | Terminal-Befehle ohne Prompt |
| Plan-Modus | `uv run eaccode --plan -p "Erstelle datei.txt"` | Schreibzugriff wird blockiert, nur Lesen erlaubt |

### C2 Cron & Daemon

| Check | Kommando | Erwartung |
|---|---|---|
| Job anlegen | `uv run eaccode cron add --every 1h "Pause machen"` | Job-ID + Liste zeigt Job |
| Sofort feuern | `uv run eaccode cron run <id>` | Nachricht kommt sofort |
| Daemon | `uv run eaccode daemon` | läuft, Log zeigt Ticks, Jobs feuern automatisch |
| Verwalten | `cron pause/resume/remove <id>` | wirkt sofort |

### C3 MCP

| Check | Kommando | Erwartung |
|---|---|---|
| Tools laden | MCP-Server in Config registrieren, `uv run eaccode mcp list` | externe Tools sichtbar |
| Tool nutzen | Prompt, der MCP-Tool braucht | Permission greift, Ausführung sichtbar |

### C4 Gateway

| Check | Kommando | Erwartung |
|---|---|---|
| Start | Bot-Token eintragen, `uv run eaccode gateway start` | Bot antwortet auf `/start` |
| Chat | Nachricht an Bot | Antwort kommt in Telegram an |
| Session | Konversation weiterführen | Kontext bleibt (Session-Mapping) |

### C5 Packaging

| Check | Kommando | Erwartung |
|---|---|---|
| Wheel | `uv build` | `.whl` + `.tar.gz` in `dist/` |
| EXE | PyInstaller-Build | `eaccode.exe --version` funktioniert (Windows) |
| Cross-Platform | Build auf Linux/macOS | gleiche Kommandos grün |

---

## Phase D — Coding-Stärke

### D1 Repo-Verständnis

| Check | Kommando | Erwartung |
|---|---|---|
| Struktur | in beliebigem Repo: `uv run eaccode -p "Struktur dieses Repos"` | korrekte Übersicht, `.gitignore` respektiert (kein `node_modules`) |
| Suche | `uv run eaccode -p "Wo wird X definiert?"` | Datei + Zeile |

### D2 Diff-Editing

| Check | Kommando | Erwartung |
|---|---|---|
| Einzel-Edit | „Ändere Funktion X so, dass …“ | Diff sichtbar, Datei korrekt, Syntax-Check grün |
| Multi-File | Änderung über 3 Dateien | alle korrekt geändert |
| Rollback | Änderung rückgängig verlangen | ursprünglicher Stand wiederhergestellt |

### D3 Test-Runner

| Check | Kommando | Erwartung |
|---|---|---|
| Loop | im Repo mit Tests: „Lass die Tests laufen und fixe Fehler“ | pytest-Läufe sichtbar, iteriert bis grün (oder klare Fehlerliste) |

### D4 Git/PR

| Check | Kommando | Erwartung |
|---|---|---|
| Workflow | „Branch feature/x, committe, öffne PR“ | Branch existiert, Commit da, PR-URL kommt zurück, PR auf GitHub prüfbar |

### D5 Coding-Routing

| Check | Kommando | Erwartung |
|---|---|---|
| Regeln | `uv run eaccode model routing show` | Routing-Tabelle |
| Routing wirkt | Coding-Prompt vs. Recherche-Prompt | Trace zeigt starkes Modell für Code, günstiges für Recherche |
| Fallback | starkes Modell abschalten | Fallback greift, kein Abbruch |

### D6 Browser-Tool

| Check | Kommando | Erwartung |
|---|---|---|
| Navigieren | `uv run eaccode -p "Öffne example.com, sag mir die Überschrift"` | korrekte Antwort |
| Screenshot | `uv run eaccode -p "Screenshot von example.com"` | Bilddatei gespeichert, öffnet |

### D0–D4: Coding-Tools (fertig, 2026-08-13)

| Check | Kommando (in eaccode-Chat) | Erwartung |
|---|---|---|
| Quote-Parsing | `/skill new probe --trigger probe --description "mit mehreren Worten"` | Beschreibung KOMPLETT gespeichert (vorher abgeschnitten) |
| `/job` im REPL | `/job list` | „(no jobs yet)" oder Job-Liste |
| `/mcp` im REPL | `/mcp list` | Roblox_Studio + weitere Server |
| Memory-Lock | 2× parallel `/memory add Test-A` / `Test-B` starten | BEIDE Einträge landen in der Datei (keiner verloren) |
| Repo-Scan | „Scanne C:\Projekte\_ref\hermes" | Struktur-Index, Größe, Dateizahl |
| Repo-Suche | „Suche in C:\Projekte\_ref\hermes nach turns_since_memory (.py)" | Treffer mit Pfad + Zeile |
| Context-Pack | „Lade den Kontext zu agent/memory_manager.py" | Modul + Tests + Imports |
| Patch-Fuzzy | „Ändere in meiner Datei: 'print(hallo)' → 'print(hi)'" (leicht abweichend) | Fuzzy-Match, Syntax-Check, Backup |
| Patch-Batch | „Ändere in X und Y ..." (2 Dateien, 2. Fehlerhaft) | Batch komplett zurückgerollt |
| Undo | „Mach den letzten Edit rückgängig" | Datei wiederhergestellt |
| Test-Runner | „Führe die Tests in C:\Projekte\eaccode-praxis aus" | Strukturierter Report (passed/failed + Fehlerliste) |
| Test-Fix-Loop | „Test test_add schlägt fehl — fixe und führe erneut aus" | rot → grün (max. 3 Zyklen) |
| Git-Status | „Git-Status in C:\Projekte\eaccode-praxis" | Saubere Zusammenfassung |
| Git-Commit | „Committe mit Message 'test'" | Commit; bei roten Tests VERWEIGERT |
| Git-Undo | „Mach den letzten Commit rückgängig" | `reset --soft HEAD~1`, Dateien bleiben |
| Übungs-Repo | `C:\Projekte\eaccode-praxis` (Bug + Tests einbauen, Agent fixen lassen) | kompletter Zyklus: scan → test rot → patch → test grün → commit |

---

## ChatApp: Layout, Palette, Turn-Marker (2026-08-17)

Slash-Palette sitzt **unter** `❯`, `●`-User-Echo, gestrichelte Linie vor `❯`,
0 leere Zeilen beim Start.

Voraussetzung: echtes Terminal (Windows-Terminal oder CMD), Breite ≥ 80.

| Check | Aktion | Erwartung |
|---|---|---|
| Start ohne LZ-Spam | `uv run eaccode` | Banner 1×, `Welcome` + `Tip`, **0 leere Zeilen**, gestrichelte Linie `─ ─ ─`, dann `❯ ▌` |
| User-Echo `●` | `hi` + Enter | `● hi` (blau fett), Agent-Antwort weiß fett, Statusline gedimmt, **1 LZ + Linie**, dann `❯` |
| Slash-Palette Position | `/` | Palette erscheint **direkt unter** `❯`, **nicht** zwischen Statusline und `❯` |
| Palette Filter | `/mem` | Sofort auf 1 Treffer gefiltert (`/memory`), ❯-Marker auf Index 0 |
| Palette Navigation | `/m` + ↓ 4× | ❯ wandert nach unten, vorherige Zeile wird wieder idle |
| Palette kein Match | `/xyz` | `(no matches)` (kursiv, gedimmt) |
| Enter 1× | `/mem` + Enter | Palette schließt, `/memory` in Buffer, `❯ /memory\|` |
| Enter 2× | dann nochmal Enter | `eaccode 0.0.1` (oder Usage), 1 LZ + Linie, `❯` |
| Slash-Command-Output | `/version` + Enter | `eaccode 0.0.1`, Linie, `❯` |
| Permission (kein Spacer) | `rm -rf /test` + Enter | `Allow: run_command … [y/N]` **ohne** 1 LZ davor, direkt `❯` |
| Permission y | `y` | `[user] y` (oder direkter Run), Statusline, Linie, `❯` |
| Stream-Verhalten | normaler Chat | Chunks streamen live in Scrollback, `❯` bleibt unten (patch_stdout) |
| Ctrl+C | Ctrl+C | `bye`, Exit 0 |

**Wichtig:** Vorher vergleichen — `abstand zu oben.md` zeigte 30+ LZ zwischen Tip
und `❯`. Nach dem Fix: 0 LZ.

---



---

## MiniMax-M3 Provider-Setup (08-17)

Voraussetzung: Anthropic-kompatibler MiniMax-Account (api.minimax.io).

| Check | Aktion | Erwartung |
|---|---|---|
| Provider-Config | `eaccode config show` | `minimax` Block enthält `base_url` = `https://api.minimax.io/anthropic` |
| Models-Liste | `eaccode model list` | `minimax/MiniMax-M3`, `minimax/MiniMax-M2.5`, `minimax/MiniMax-M2.1`, `minimax/MiniMax-M2.1-lightning` |
| Live-Ping | `eaccode model ping minimax/MiniMax-M3` | Antwort enthält `pong` (Reasoning + Antwort beide sichtbar) |
| Stream-Test | `eaccode`, dann `hi` | `[Reasoning: ...]` (italic muted) gefolgt von Antwort in normalem Style |
| Antwort-Vollständigkeit | `eaccode`, dann `was kannst du?` | Antwort kommt **vollständig**, nicht mitten im Satz abgeschnitten |
| Token-Stats | Status-Zeile | `MiniMax-M3 │ X.Ys │ NNN chars` (nicht "0 chars") |
| Fallback | `minimax` API-Key ungültig setzen, dann chatten | Fallback zu `ollama/llama3.2` greift |



---

## Provider-Switch zu Anthropic-SDK (08-17)

Die eaccode-Architektur ist jetzt LiteLLM-frei. Anthropic-Messages-kompatible Provider (MiniMax, Anthropic) gehen direkt über das `anthropic` SDK, andere sind out of scope.

### Verifikation

1. **Test, dass LiteLLM wirklich weg ist:**
   ```bash
   grep -rn "litellm" src/eaccode/ 2>&1 | head -3
   # Erwartung: KEINE Treffer
   ```

2. **Test, dass models.dev funktioniert:**
   ```bash
   export PYTHONPATH= && uv run python -c "
   import sys; sys.path.insert(0, 'src')
   from eaccode import models_dev
   info = models_dev.get_model_info('minimax', 'MiniMax-M3')
   print(f'context={info.context_window}, max_out={info.max_output}, reasoning={info.reasoning}')
   print(f'cost=\${info.cost_input}/M in, \${info.cost_output}/M out')
   "
   # Erwartung: context=1000000, max_out=128000, reasoning=True
   #           cost=$0.30/M in, $1.20/M out
   ```

3. **Test, dass Provider-Registry funktional ist:**
   ```bash
   export PYTHONPATH= && uv run pytest tests/test_providers_anthropic.py tests/test_providers_registry.py -q
   # Erwartung: 43 passed (27 + 16)
   ```

4. **Test, dass Disk-Cache funktioniert:**
   ```bash
   cat C:/Users/kurtj/AppData/Local/eaccode/models_dev_cache.json | head -10
   # Erwartung: JSON mit 7 MiniMax-Modelle
   ```

5. **Live-Test MiniMax via eaccode:**
   ```bash
   eaccode
   # Dann im REPL:
   # > hi
   # Erwartung: Vollständige Antwort, NICHT mitten im Satz abgeschnitten
   ```

## Fehler melden (wichtig für die Zusammenarbeit)

Wenn ein Check fehlschlägt, schick mir **genau diese drei Dinge**:

1. Das ausgeführte Kommando
2. Die echte Ausgabe (Copy-Paste, nicht beschreiben)
3. Erwartung vs. tatsächliches Ergebnis

Damit kann ich reproduzieren und fixen — ohne Ratespiel.
