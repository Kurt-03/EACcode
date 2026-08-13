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

---

## Phase B — Hermes-Core

### B1 Skill-System

| Check | Kommando | Erwartung |
|---|---|---|
| Liste | `uv run eaccode skills list` | vorhandene Skills mit Beschreibung |
| Trigger | Prompt, der einen Skill-Trigger enthält | Skill wird geladen (im Trace sichtbar) |

### B2 Learning-Loop ⭐ (Herzstück)

| Check | Kommando | Erwartung |
|---|---|---|
| Skill entsteht | komplexen Task geben (z. B. „Schreibe Skript, das …“) | nach Abschluss: neuer Skill in `skills list` |
| Skill wird genutzt | denselben Task erneut geben | Trace zeigt Skill-Load (schneller/besser) |
| Skill verbessert sich | Task mit leichtem Twist dritteln | `skills show <name>` zeigt Verbesserung |

### B3 Session-Store

| Check | Kommando | Erwartung |
|---|---|---|
| Sessions | 2 Gespräche führen, dann `uv run eaccode sessions list` | beide sichtbar |
| Suche | `uv run eaccode sessions search "Stichwort"` | Treffer mit Kontext-Snippet |
| Link | `@session:<id>` in neuem Chat einfügen | Agent hat Kontext aus alter Session |

### B4 Memory-Hierarchie

| Check | Kommando | Erwartung |
|---|---|---|
| Projekt-Memory | im Repo arbeiten, Fakt merken | Eintrag landet projektbezogen, nicht global |
| Budget | Memory fast voll | automatische Kuration (alte Einträge werden konsolidiert) |
| Konflikt | gleichen Fakt mit neuem Wert merken | Update, kein Duplikat |

### B5 Subagents

| Check | Kommando | Erwartung |
|---|---|---|
| Parallel | „Starte 2 Subagenten: Gedicht über Katzen + über Hunde, fasse zusammen“ | beide Ergebnisse kommen zurück |
| Limit | 10 gleichzeitig anfordern | max. 6 parallel, Rest wartet |

### B6 Parallel-Execution

| Check | Kommando | Erwartung |
|---|---|---|
| Parallele Calls | Prompt mit mehreren unabhängigen Tool-Calls | Log zeigt überlappende Timestamps |
| Fehler-Isolation | ein Tool schlägt fehl | andere laufen weiter, Fehler separat gemeldet |

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

---

## Fehler melden (wichtig für die Zusammenarbeit)

Wenn ein Check fehlschlägt, schick mir **genau diese drei Dinge**:

1. Das ausgeführte Kommando
2. Die echte Ausgabe (Copy-Paste, nicht beschreiben)
3. Erwartung vs. tatsächliches Ergebnis

Damit kann ich reproduzieren und fixen — ohne Ratespiel.
