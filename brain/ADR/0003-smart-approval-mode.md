---
number: 0003
title: Smart Approval Mode with Aux LLM
status: accepted
date: 2026-08-18
---

# ADR 0003: Smart Approval Mode mit Aux LLM

## Kontext

Bis 08-18 hatte eaccode ein einfaches `ask` (default) / `allow_all` / `read_only` /
`deny_all` System. Effekt:

- **8 Permission-Prompts pro triviale Aufgabe** (User-Screenshot 08-18, erste Session).
- Model probierte 8 verschiedene Wege, bevor es aufgab.
- Hoher Frust bei Low-Risk-Operationen wie `echo "test"`.

Hermes verwendet stattdessen `manual` / `smart` / `off` Modi mit Aux-LLM
Risk-Assessment für `smart`. **Battle-tested.**

## Entscheidung

Wir adoptieren den Hermes-Approach verbatim:

1. **Drei Modi**: `manual | smart | off` (+ `read_only` für
   Backward-Compat).
2. **89 Patterns** (12 hardline + 77 dangerous), 1:1 von Hermes übernommen.
3. **Aux-LLM** = das aktive Haupt-Agent-Model (kein separates Model
   initially).
4. **Slash-Command** `/approvals` zeigt/wechselt Mode.
5. **Default-Mode**: `smart`.

## Konsequenzen

### Pro
- Drop von 5-10 Prompts pro Session auf 0-2 für normale Arbeit.
- Sicherheit bleibt: hardline blockt immer, dangerous → aux LLM bewertet.
- Hermes-Verbatim = klare Referenz-Implementation.

### Contra
- Aux-LLM-Calls kosten Tokens (~500 token pro dangerous command).
- `off`-Mode = yolo. Der User **muss** es aktiv setzen.
- Kein separates Modell ⇒ Quality-Schwankungen je nach Modell-Stärke.

## Alternativen

- **Pattern-only** (ohne LLM): zu starr, viele False-Positives.
- **ML-Modell (Hugging Face lokal)**: overkill für Solo-Dev.
- **Multi-Aux-LLMs**: kommt in Phase 2 wenn User verschiedene Modelle
  will.

## Implementierung

- `src/eaccode/permissions.py` — `PermissionManager` (Smart/Manual/Off Pipeline)
- `src/eaccode/smart_approval.py` — `SmartApprovalReviewer` (Worker-Thread, Timeout 10s)
- `src/eaccode/palette.py` — `_cmd_approvals` Slash-Command
- `src/eaccode/cli.py` — `SmartApprovalReviewer` setup in `build_agent()`

## Tests

- `tests/test_permissions.py` — 42 Tests
- `tests/test_smart_approval.py` — 23 Tests

## Status

Accepted — code shipped via Phase D + 08-18.

## Verwandt

- [[15-features/system/permissions.md|permissions]]
- [[15-features/system/smart-approval.md|smart-approval]]
- [[15-features/commands/approvals.md|approvals]]
- [[15-features/commands/permissions.md|permissions]]
- Plan: `.hermes/plans/2026-08-18_071745-smart-approval-mode.md`
