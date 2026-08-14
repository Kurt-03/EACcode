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
- Modus-Injection ✅: im read_only-Modus versucht der Agent Schreib-Tools
  gar nicht erst (System-Prompt-Hinweis)
- **ask-Semantik (Nachbesserung 2026-08-13):** lesende Tools
  (read_file/web/current_time/Sessions) laufen **frei** ohne Prompt —
  nur mutierende Tools fragen (Regression aus C1 behoben, live bewiesen:
  current_time antwortet ohne Prompt)
- **Session-Allow + Gefahrenklassen (2026-08-14):** Routine-Tools
  (write_file, memory, skills, git_commit, run_tests, subagents) fragen
  **EINMAL pro Session** — nach Zustimmung laufen sie frei bis zum
  Neustart. Kritische Tools (run_command, Browser-Aktionen, mutierende
  MCP-Calls) fragen **bei JEDEM Call**. Lesende MCP-Tools laufen frei
  (Namens-Heuristik: get_/list_/read/search/inspect/grep/scan/...).
  git_status/log/diff + browser_status sind jetzt read-only.
  `session_allow/session_clear/session_allowed()` im Manager;
  Mode-Hint erklärt die Semantik (Agent antwortete live korrekt:
  „nach deiner Zustimmung brauche ich keine erneute Freigabe")

## Tests
`tests/test_permissions.py` (19: Modes, Regeln, Persistenz, mode_hint,
ask-readonly-frei) + Agent-Gate-Tests (test_agent)
+ `TestSessionAllow` (7: Session-Merkung, kritische Tools immer, MCP
read-only frei, deny gewinnt, session_clear)

## Offene Punkte
- Echte Sandbox (Docker/bwrap) — optional, später
- Regel-Syntax-Erweiterung (Glob statt Regex) — nach Nutzerfeedback
- MCP readOnlyHint aus dem Protokoll statt Namens-Heuristik (ideal)

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/permission-gate.md|Permission-Gate]] · [[15-features/system/agent-core.md|Agent Core]]

## Code-Graph (generiert)

- `src/eaccode/permissions.py` → [[15-features/system/config.md|config.yaml]]

