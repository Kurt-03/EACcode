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

- **0001** — [[ADR/0001-config-yaml-design.md\|0001-config-yaml-design]] · 2026-08-13
- **0002** — [[ADR/0002-phase-a-architecture.md\|0002-phase-a-architecture]] (Router, Loop, Memory, TUI) · 2026-08-13
- **0003** — Smart Approval Mode mit Aux LLM · 2026-08-18 (siehe
  [[15-features/system/permissions.md\|permissions]] + [[15-features/system/smart-approval.md\|smart-approval]])
- **0004** — LiteLLM out, Anthropic-SDK direkt · 2026-08-17 (siehe
  [[15-features/system/providers.md\|providers]] + [[ADR/0004-litellm-to-anthropic-sdk.md\|0004-litellm-to-anthropic-sdk]])
- **0005** — Workspace-Sandbox-Architektur (Plan H.minimal) · 2026-08-18
  (siehe [[15-features/system/workspace.md\|workspace]] + [[ADR/0005-workspace-sandbox.md\|0005-workspace-sandbox]])
- **0006** — Permission Deep-Hardening (Plan C, Hermes-Voll, 5 Outcomes) ·
  2026-08-18 (siehe [[15-features/system/permissions.md\|permissions]])
- **0007** — Hermes-Safety-Hardening (Plan D, 16 must-have Features) ·
  2026-08-18 (siehe [[15-features/system/permissions.md\|permissions]])

### Kurz-Stand der ADR-Plan-Verdichtung

| Plan | Hermes-Coverage | Notiz-Spine |
|---|---|---|
| Plan A | Tool-Property-Descriptions, `mutates`-Tag | (in `permissions.md` Plan B-Abschnitt) |
| Plan B | Sensitive-Path + Always-Ask-Enforcement | (in `permissions.md` Plan B-Abschnitt) |
| Plan C | Smart-Mode 5 Outcomes, persistent Blocklist, Path-Symlink-Resolve, Exit-Code-Warnings | [[15-features/system/permissions.md\|permissions]] |
| Plan D | Tirith, file_safety, sudo-guard, runtime_context, blocked-list, human-wait-window | [[15-features/system/permissions.md\|permissions]] + [[15-features/system/tirith-security.md\|tirith-security]] + [[15-features/system/file_safety.md\|file_safety]] + [[15-features/system/blocked-list.md\|blocked-list]] + [[15-features/system/human-wait-window.md\|human-wait-window]] |
| Plan G v5 | Tool-Architecture 12 Module | [[15-features/system/tool-architecture.md\|tool-architecture]] |
| Plan G v6 | U1 Tool-Calls-DB-Persistenz | (in `store.py` schema migration) |
| Plan H.minimal | Workspace-Sandbox 3 Stufen | [[15-features/system/workspace.md\|workspace]] + [[15-features/system/path-security.md\|path-security]] + [[15-features/system/write-approval.md\|write-approval]] + [[15-features/system/container.md\|container]] |

## Projekt-Kurzstand (2026-08-18)

- **Phase A (Foundation) ✅** · **Phase B (Hermes-Core) ✅** · **C1–C3 ✅**
  (C4 Gateway/Telegram + C5 Packaging bewusst auf später verschoben) ·
  **Phase D (Coding-Stärke) ✅ KOMPLETT** · **Phase E (Smart Approval) ✅** ·
  **Phase F (Deep Permission Hardening) ✅** · **Phase G (Tool Architecture
  Hermes-Verbatim) ✅ v5+v6** · **Phase H (Workspace-Sandbox) ✅ Stufe 1+2** ·
  Stufe 3 (Container) ist **code-ready aber opt-in**
- **988 Tests grün** (Stand 08-18, Plan H Audit-Phase `146ffce`), +380 seit 08-17
- **52 src-Module** im Code, **45+ dedizierte Brain-Notizen** (jedes Tool-G + Plan-H-Modul einzeln)
- Agent kann heute: Skills lernen, Sessions durchsuchen, Memory kuratieren,
  Subagents parallel, **Smart Permissions** (5 Outcomes + Aux LLM + Owner-Override
  + Secret-Redaction), MCP (mit Description-Scan gegen Prompt-Injection),
  Repo-Verständnis, Diff-Editing, Tests laufen lassen, Git/PR,
  Browser-Steuerung, **models.dev Catalog** (4000+ Models), **Workspace-Sandbox**
  (cwd = workspace + `/approvals allow-path` + Container-Backend opt-in),
  **Tirith External Scanner** mit SHA-256 + Cosign
- `run_command` ist 08-18 komplett aus dem Code entfernt (Commit `11faf9c`)
- Repo: `C:\Projekte\EACcode V3` · Remote: `github.com:Kurt-03/EACcode` (gepusht 2026-08-18)

## Offene Entscheidungen (Auszug)

- C4 Gateway/Telegram + C5 Packaging: **später** (Nutzer-Entscheid)
- Plan H Stufe 4: Image-Caching + cgroups-Resource-Limits (in Code, noch nicht
  verdrahtet)
- D5 Coding-Routing (LLM-Router anhand Repo-State) — Idee, nicht spezifiziert
- Hermes-Adapter für OpenAI-Compat-Provider (OpenRouter, Ollama wieder aktivieren)
- OpenAI/Ollama-Provider-Re-Aktivierung (Post-LiteLLM-Exit OpenAI-compat-Adapter fehlt)
- Stuck at MiniMax OAuth-tokens perimeter ab 08-13 (separat tracken)
- H22 Two-Layer Pre-Execution Guards (Tirith + dangerous patterns combined) — in-progress
- H17/H19 classification categories / `raise_if_read_blocked` — Hermes-spezifisch, deferred
- Background-Review (Hermes-Learning-Loop) — nach Cron existent, noch offen

---
*Zuletzt gepflegt: 2026-08-18 (Plan H Audit-Phase + Workspace-Sandbox-Notes + 988 Tests grün)*
