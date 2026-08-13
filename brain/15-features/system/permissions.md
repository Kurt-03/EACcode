---
name: permissions
type: system
status: active
phase: C1
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Permission-/Sandbox-System (C1)

## Zweck
Regel-basierte Zugriffskontrolle für ALLE Agent-Tools: Modes (ask/allow_all/
read_only/deny_all), allow-/deny-Regeln (Regex auf Tool-Call), Sandbox
(Docker optional; Windows-sicher = Modus-Schutz statt Kernel-Sandbox).

## Implementierung
- `src/eaccode/permissions.py` — `PermissionManager` (Regeln > Modus > ask)
- Agent-Loop prüft **jedes Tool** vor der Ausführung (Nachbesserung zu A5,
  wo nur `run_command` geprüft wurde)
- config.yaml: `permissions: {mode, allow[], deny[]}` + `/permissions`-Kommando
- Sandbox: dokumentiert, nicht implementiert (Docker optional, C-Phase)

## Verifiziert (live, 2026-08-13)
- (wird beim Live-Test ergänzt)

## Tests
`tests/test_permissions.py` + Agent-Integrationstests

## Offene Punkte
- Echte Sandbox (Docker/bwrap) — optional, später
- Regel-Syntax-Erweiterung (Glob statt Regex) — nach Nutzerfeedback

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/permission-gate.md|Permission-Gate]] · [[15-features/system/agent-core.md|Agent Core]]
