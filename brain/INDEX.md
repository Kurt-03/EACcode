# eaccode Brain — Index (Map of Content)

Wissenszentrale des eaccode-Projekts — gepflegt nach dem **LLM-Wiki-Muster**
(Karpathy): Der Agent integriert neue Erkenntnisse in bestehende Seiten,
statt nur anzuhängen. Das Wiki kompiliert Wissen einmal und hält es aktuell.

> **Regeln:** siehe [[README.md|Vault-Handbuch]]. Kern: Fakten sind *timeless*,
> *dated* oder *Pointer* — nie eine undatierte „aktuelle" Behauptung.

## Einstieg

| Bereich | Inhalt |
|---|---|
| [[15-features/README.md\|Feature-Register]] | **Feature-Register**: jedes Feature einzeln getrackt (Tools, Provider, System, Commands, Agents) |
| [[10-projects/README.md\|Dashboard]] | Dashboard: aktive Phase, nächste Schritte, offene Entscheidungen |
| [[10-projects/phase-d.md\|phase-d]] | Phase D: Coding-Stärke (D0–D6, DoD) |
| [[20-areas/architecture.md\|Architektur]] · [[20-areas/vision.md\|Vision]] · [[20-areas/tooling.md\|Tooling]] · [[20-areas/testing.md\|Testing]] | Dauerhaftes Wissen |
| [[30-research/README.md\|Research]] | Evaluierungen mit Datum, Kriterien, Ergebnis |
| [[ADR/0002-phase-a-architecture.md\|0002-phase-a-architecture]] | Entscheidungslog (Kontext → Entscheidung → Konsequenz) |
| [[50-archive/phase-a.md\|Phase A]] · [[50-archive/phase-b.md\|phase-b]] | Abgeschlossene Phasen (dated snapshots) |
| [[wiki/README.md\|Wiki]] | LLM-gepflegte Querverweise, Logs (ab Phase B aktiv) |
| **Test-Map** | fortlaufende „wie wird was getestet"-Liste → `docs/test-map.md` im Repo |

## Aktuelle Entscheidungen (ADR)

- **0002** — [[ADR/0002-phase-a-architecture.md|0002-phase-a-architecture]] (Router, Loop, Memory, TUI) · 2026-08-13
- **0001** — [[ADR/0001-config-yaml-design.md|0001-config-yaml-design]] · 2026-08-13

## Projekt-Kurzstand (2026-08-13)

- **Phase A (Foundation) ✅** · **Phase B (Hermes-Core) ✅** · **C1–C3 ✅**
  (C4/C5 bewusst auf später verschoben) · **Phase D (Coding-Stärke) ✅ KOMPLETT**
  — DoD erfüllt (Übungs-Repo: Issue → Implementierung → Suite → Commit, live)
- **402 Tests grün** + ruff clean; Live-Verifikationen zu jeder Phase
  (Test-Map + manual-test.md im Repo)
- Agent kann heute: Skills lernen, Sessions durchsuchen, Memory kuratieren,
  Subagents parallel, Permissions, MCP (Roblox Studio), Repo-Verständnis,
  Diff-Editing, Tests laufen lassen, Git/PR, Browser-Steuerung
- Repo: `C:\Projekte\EACcode V3` · Remote: `github.com/Kurt-03/EACcode` (gepusht 2026-08-13)

## Offene Entscheidungen (Auszug)

- C4 Gateway/Telegram + C5 Packaging: **später** (Nutzer)
- Optionale Ideen (nur auf Nachfrage): D5 Coding-Routing, Toolset-Gruppierung
  → [[10-projects/phase-d.md|phase-d]]
- Background-Review (Hermes-Learning-Loop) — nach Cron existent, noch offen
- GitHub-Remote: gesetzt + gepusht (alte `eac-code`-Remote ist Geschichte)

---
*Zuletzt gepflegt: 2026-08-13 (Stand: Phase D KOMPLETT, 402 Tests, Repo gepusht)*
