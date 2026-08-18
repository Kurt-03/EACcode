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
- **0001** — [[ADR/0001-config-yaml-design.md|0001-config-yaml-config]] · 2026-08-13
- **ADR-0003** *(geplant)* — Smart Approval Mode mit Aux LLM (08-18) — siehe
  [[15-features/system/permissions.md|permissions]] + [[15-features/system/smart-approval.md|smart-approval]]
- **ADR-0004** *(geplant)* — LiteLLM out, Anthropic SDK direkt (08-17) —
  siehe [[15-features/system/providers.md|providers]]
- **ADR-0005** *(geplant)* — Tool-Schema-Audit + Permission-Hardening (08-18) —
  siehe [[15-features/system/permissions.md|permissions]]
- **ADR-0006** *(geplant)* — Permission Deep-Hardening (Plan C, Hermes-Voll) (08-18) -
- **ADR-0007** *(geplant)* — Hermes-Safety-Hardening (Plan D, 16 von 16 must-have Features) (08-18) —
  siehe [[15-features/system/permissions.md#08-18-plan-c-audit-hardening-2|Plan C]]

### Permission Deep-Hardening (08-18)

5 Outcomes: once / session / always / deny / deny_always / timeout. Hermesische
[[15-features/system/permissions.md|Permission-Pipeline]] mit Secret-Redaction,
Owner-Override-Aux-LLM, persistent Deny_Always-Blocklist, Path-Symlink-Resolve,
Exit-Code-Warnings. 641 Tests grün. Inline-Prompt-UX mit 5 Options ([y/s/a/n/A]) + Echo.
  siehe [[15-features/system/providers.md|providers]]

## Projekt-Kurzstand (2026-08-18)

- **Phase A (Foundation) ✅** · **Phase B (Hermes-Core) ✅** · **C1–C3 ✅**
  (C4/C5 bewusst auf später verschoben) · **Phase D (Coding-Stärke) ✅ KOMPLETT**
- **08-17:** LiteLLM raus, Anthropic-SDK rein. Catalog via models.dev.
- **08-18:** Smart Approval (Hermes-kompatibel 3 Modi + Aux LLM, default `smart`) +
  Streaming-Bug-Fix (Buffer-Accumulator für REPL)
- **609 Tests grün** · Plan A (Tool-Property-Descriptions + mutates-Tag) und Plan B (Permission-Hardening: sensitive-path, always_ask enforcement) sind gefixt
- Smart-mode jetzt safe für .ssh/.env/config.yaml writes (vorher silent approved) + ruff clean; Live-Verifikationen zu jeder Phase
  (manual-test.md im Repo)
- Agent kann heute: Skills lernen, Sessions durchsuchen, Memory kuratieren,
  Subagents parallel, **Smart Permissions**, MCP (Roblox Studio), Repo-Verständnis,
  Diff-Editing, Tests laufen lassen, Git/PR, Browser-Steuerung,
  **models.dev Catalog** (4000+ Models)
- Repo: `C:\Projekte\EACcode V3` · Remote: `github.com:Kurt-03/EACcode` (gepusht 2026-08-18)

## Offene Entscheidungen (Auszug)

- C4 Gateway/Telegram + C5 Packaging: **später** (Nutzer)
- Optionale Ideen (nur auf Nachfrage): D5 Coding-Routing, Toolset-Gruppierung
  → [[10-projects/phase-d.md|phase-d]]
- Background-Review (Hermes-Learning-Loop) — nach Cron existent, noch offen
- GitHub-Remote: gesetzt + gepusht (alte `eac-code`-Remote ist Geschichte)

---
*Zuletzt gepflegt: 2026-08-18 (Smart Approval + Streaming-Bug-Fix + Anthropic-SDK, 578 Tests, gepusht)*
