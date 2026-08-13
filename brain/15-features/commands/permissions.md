---
name: command-permissions
type: command
phase: C1
date: 2026-08-13
tags: [type/feature, feature/command]
---

# Command: /permissions

## Zweck
Permission-Modi und Regeln im REPL verwalten (CLI-Äquivalent:
`eaccode permissions …`).

## Syntax
```
/permissions status
/permissions mode <ask|allow_all|read_only|deny_all>
/permissions allow <regex>
/permissions deny <regex>
/permissions unallow <regex>
/permissions undeny <regex>
/permissions reset
```

## Details
- Default `ask`: lesende Tools laufen frei, mutierende fragen interaktiv
- `read_only`/`deny_all` werden in den System-Prompt injiziert (der Agent
  weiß vorab Bescheid)
- deny-Regeln gewinnen immer gegen allow-Regeln

## Verknüpft
[[15-features/system/permissions.md|permissions]] · [[15-features/commands/README.md|README]]
