# eaccode Brain — Index (Map of Content)

Wissenszentrale des eaccode-Projekts — gepflegt nach dem **LLM-Wiki-Muster**
(Karpathy): Der Agent integriert neue Erkenntnisse in bestehende Seiten,
statt nur anzuhängen. Das Wiki kompiliert Wissen einmal und hält es aktuell.

> **Regeln:** siehe [[README|Vault-Handbuch]]. Kern: Fakten sind *timeless*,
> *dated* oder *Pointer* — nie eine undatierte „aktuelle" Behauptung.

## Einstieg

| Bereich | Inhalt |
|---|---|
| [[15-features/README\|Features]] | **Feature-Register**: jedes Feature einzeln getrackt (Tools, Provider, System, Agents) |
| [[10-projects/README\|Projekte]] | Dashboard: aktive Phase, nächste Schritte, offene Entscheidungen |
| [[20-areas/architecture\|Areas]] | Dauerhaftes Wissen: Architektur, Vision, Tooling, Testing |
| [[30-research/README\|Research]] | Evaluierungen mit Datum, Kriterien, Ergebnis |
| [[adr/0002-phase-a-architecture\|ADR]] | Entscheidungslog (Kontext → Entscheidung → Konsequenz) |
| [[50-archive/phase-a\|Archiv]] | Abgeschlossene Phasen (dated snapshots) |
| [[wiki/README\|Wiki]] | LLM-gepflegte Querverweise, Logs (ab Phase B aktiv) |

## Aktuelle Entscheidungen (ADR)

- **0002** — [[adr/0002-phase-a-architecture|Phase-A-Architektur]] (Router, Loop, Memory, TUI) · 2026-08-13
- **0001** — [[adr/0001-config-yaml-design|config.yaml + Secrets-Design]] · 2026-08-13

## Projekt-Kurzstand

- **Phase A (Foundation & MVP) komplett ✅** — v0.0.1, 150 Tests, chatfähig (REPL + TUI)
- **Als Nächstes: Phase B (Hermes-Core)** — Skills + Learning-Loop, Session-Suche, Subagents → [[10-projects/phase-b|Skizze]]
- Repo: `C:\Projekte\EACcode V3` · Master-Plan: `.hermes/plans/2026-08-13_130000-eaccode-v2-master-plan.md`

## Offene Entscheidungen (Auszug)

- Provider-Erstauslieferung (O2) · Display-Name (O3) · Dev-Python (O4) → [[10-projects/README|Dashboard]]

---
*Zuletzt gepflegt: 2026-08-13 (Phase A abgeschlossen, Brain neu strukturiert)*
