---
name: git-pr
type: system
status: done
phase: D4
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Git & PR (D4)

## Zweck
Der Agent arbeitet mit Git: Status/Diff/Log ansehen, committen (Policy:
nie bei roten Tests), Branches, PRs via gh CLI.

## Implementierung
- `src/eaccode/git.py` — `_git`-Wrapper (subprocess, Timeout, saubere
  Fehler), `git_status/diff/log/branch` (read-only), `git_commit`
  (add -A + commit, Policy-Hinweis), `git_commit_undo` (reset --soft,
  nur letzter Commit), `git_branch_new`, `git_push`, `git_pr`
  (gh CLI optional, sonst Anleitung)
- Tools: `git_status`, `git_diff`, `git_log`, `git_commit`,
  `git_branch_new`, `git_commit_undo` — mutierend (ask)

## Verifiziert (live, 2026-08-13 — Übungs-Repo)
- Agent committete „feat: add multiply function" nach grüner Suite
- Policy-Verhalten: verweigerte Commit bei roten Tests + No-op-Commits

## Tests
`tests/test_git.py` (12: Status, Commit, Undo, Branches, Tools — echtes git)

## Offene Punkte
- gh CLI ist nicht installiert (PR-Pfad zeigt Anleitung) — bei Bedarf

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/test-runner.md|test-runner]] · [[15-features/system/diff-editing.md|diff-editing]]

## Code-Graph (generiert)

- `src/eaccode/git.py` → [[15-features/system/agent-core.md|Agent Core]]

