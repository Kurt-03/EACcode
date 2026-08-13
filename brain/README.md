# eaccode Brain — Vault-Handbuch

Dieses Vault ist die **Wissenszentrale des eaccode-Projekts**. Es wird von
Menschen und Agents gemeinsam gepflegt (Hermes heute, eaccode selbst ab
Phase B). Es folgt dem **LLM-Wiki-Muster** (Karpathy): Wissen wird einmal
kompiliert und *aktuell gehalten* — Seiten werden bei neuen Erkenntnissen
aktualisiert, nicht nur erweitert.

## Die Fakten-Regel (OKM — Open Knowledge Metabolism)

Jede Notiz ist genau eine von drei Formen:

1. **Timeless** — kein Datum nötig, verfällt nicht
   `Die Architektur ist in drei Schichten organisiert.`
2. **Snapshot** — datiert, behauptet nur „was an Datum X wahr war"
   `2026-08-13: Phase A abgeschlossen, 150 Tests grün.`
3. **Pointer** — wo die Wahrheit lebt (+ letzter Stand mit Datum)
   `Aktueller Teststand: Repo (uv run pytest). Stand 2026-08-13: 150 passed.`

**Illegal:** eine undatierte Gegenwarts-Behauptung über etwas, das sich ändert
(„Die Tests sind grün", „Es gibt 5 Provider"). → Pointer oder Datum.

**Slow vs. fast facts:** Wie das System gebaut ist, gehört hierher. Live-Zahlen
(Teststände, Commits, Key-Status) bleiben Pointer auf das Repo.

## Ordner-Layout (code-ähnlich)

| Ordner | Rolle | Wann anlegen |
|---|---|---|
| `00-inbox/` | Schnell-Erfassung | jederzeit; wird bei Kuration sortiert |
| `10-projects/` | Aktive Arbeitsstränge + Dashboard | Phase startet / ändert sich |
| `15-features/` | **Feature-Register**: eine Notiz pro Feature | **jedes neue Feature** (Tool, Provider, System, Agent) |
| `20-areas/` | Dauerhaftes Wissen (Architektur, Vision, …) | Wissen entsteht |
| `30-research/` | Evaluierungen (immer dated) | vor Entscheidungen |
| `40-people/` | Personen-Kontext (User, Contributors) | Person relevant wird |
| `50-archive/` | Abgeschlossenes (dated snapshots) | Phase endet |
| `adr/` | Entscheidungslog `NNNN-titel.md` | Architektur-Entscheidung |
| `wiki/` | LLM-gepflegte Seiten + `logs/` (datiert) | ab Phase B |
| `_templates/` | Notiz-Templates | — |

## Feature-Regel

**Jedes Feature bekommt eine eigene Notiz in `15-features/`** (`tools/`,
`providers/`, `system/`, `agents/`) mit Frontmatter (name/type/status/phase)
und einen Eintrag in der Register-Tabelle. Status: `planned → active → done`.
Neue Features → Template `_templates/feature.md` verwenden.

## Schreibregeln

- **Frontmatter** (`date`, `status`, `tags`) — siehe `_templates/`.
- **Wikilinks immer mit Pfad vom Vault-Root + Alias:**
  `[[15-features/system/repl.md|REPL]]` — nie Kurznamen, nie `../`-Pfade.
  In Markdown-Tabellen: `\|` als Escape verwenden.
- **Wikilinks statt Duplikate:** Pläne/Tasks/Code-Doku leben im Repo;
  hier wird *verlinkt*, nicht kopiert.
- **Eine Idee pro Notiz** (Atomic Notes) — so bleiben Links sauber.
- **Tags:** `#area/<name>` · `#status/<active|done|archived>` · `#type/<adr|research|log>`.
- **Der Agent pflegt:** Neue Erkenntnisse aktualisieren bestehende Seiten
  (update statt append) und verschieben Inbox-Notizen in ihre Bereiche.

## Workflow (kurz)

1. Schneller Gedanke → `00-inbox/` (ein Satz reicht)
2. Kuration (wöchentlich oder nach Steps) → Bereich, verlinkt, Fakten-Regel geprüft
3. Architektur-Entscheidung → `adr/` + Eintrag im [[INDEX.md|Index]]
4. Phase abgeschlossen → Abschluss-Snapshot nach `50-archive/`
