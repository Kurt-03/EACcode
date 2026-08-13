---
name: permissions
type: system
status: done
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
- `src/eaccode/permissions.py` — `PermissionManager` (deny-Regeln >
  allow-Regeln > Modus > ask-Handler)
- Agent-Loop prüft **jedes Tool** vor der Ausführung (Nachbesserung zu A5,
  wo nur `run_command` geprüft wurde); run_command überspringt seinen
  eigenen zweiten Prompt via threading.local-Marker
- config.yaml: `permissions: {mode, allow[], deny[]}` + `/permissions` +
  `eaccode permissions` (status, mode, allow, deny, unallow, undeny, reset)
- Sandbox: dokumentiert, nicht implementiert (Docker optional)

## Verifiziert (live, 2026-08-13)
- `mode read_only` → Agent-Deny mit Erklärung (write_file blockiert)
- `mode ask` → interaktiver Prompt `Allow: write_file {…} [y/N]`
- allow-Regel `mcp__fake__echo` erlaubte gezielt ein MCP-Tool

## Tests
`tests/test_permissions.py` (14) + Agent-Gate-Tests (test_agent)

## Offene Punkte
- Echte Sandbox (Docker/bwrap) — optional, später
- Regel-Syntax-Erweiterung (Glob statt Regex) — nach Nutzerfeedback

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/permission-gate.md|Permission-Gate]] · [[15-features/system/agent-core.md|Agent Core]]
