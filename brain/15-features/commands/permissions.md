---
status: done
name: command-permissions
type: command
phase: C1 + 08-18
date: 2026-08-13 / updated 2026-08-18
tags: [type/feature, feature/command]
---

# Command: /permissions

## Zweck
Permission-Modi und Regeln im REPL verwalten (CLI-Äquivalent:
`eaccode permissions …`).

**Phase:** C1 (08-13, 4 Modi), 08-18 (Hermes-Migration auf 3 Modi + smart)

## Syntax
```
/permissions status
/permissions mode <manual|smart|off|read_only>
/permissions allow <regex>
/permissions deny <regex>
/permissions unallow <regex>
/permissions undeny <regex>
/permissions reset
```

**Modi (Hermes-Verbatim ab 08-18):**
- `manual` (alias `ask`): jede mutating Action fragt User
- `smart` (NEU 08-18, **default**): safe auto-approve; gefährliche Befehle an Aux-LLM
- `off` (alias `allow_all`): alle auto-approve, hardline bleibt blockiert
- `read_only`: nur Read-Tools

**Quick-Switch für Mode:** `/approvals [manual|smart|off]`

## Details
- Default seit 08-18 ist `smart`
- Hardline-Patterns (12, Hermes-Verbatim) blocken IMMER, auch in `off`
- Dangerous-Patterns (77) gehen in `smart` mode an Aux LLM
- deny-Regeln gewinnen immer gegen allow-Regeln
- `_MODE_ALIASES` normalisiert `ask` → `manual`, `allow_all` → `off`
- Siehe `[[15-features/system/smart-approval.md|smart-approval]]` für Details

## Verknüpft
[[15-features/system/permissions.md|permissions]] ·
[[15-features/system/smart-approval.md|smart-approval]] ·
[[15-features/commands/approvals.md|approvals]]
