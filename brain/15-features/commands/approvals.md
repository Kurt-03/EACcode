---
name: approvals-slash-cmd
type: command
status: done
phase: 08-18 smart
tags: [type/command, approvals, security]
---

# Command: `/approvals` (Smart Mode Switch)

> **Phase:** 08-18 Smart Approval Mode
> **Use:** Shows current approval mode; optional switch argument.

## Usage

```
/approvals                  # show current mode + allow/deny rules
/approvals manual           # switch to manual (ask on every tool call)
/approvals smart            # switch to smart (auto + aux LLM risk-assessment)
/approvals off              # switch to off (yolo, hardline still blocks)
/approvals read_only        # switch to read-only (blocks all mutating tools)
```

## Effective Mode

Displays the **resolved** mode after alias normalization:

| Config value | Alias of |
|-------------|----------|
| `ask` | `manual` |
| `allow_all` | `off` |
| `manual` | (as-is) |
| `off` | (as-is) |
| `smart` | (as-is) |
| `read_only` | (as-is) |

## Output

Example session in smart mode:

```
mode: smart (effective: smart)
allow: []
deny: []
```

## Implementation

`src/eaccode/palette.py:_cmd_approvals` calls
`commands.run_permissions_command([...])` with stdout captured into a
StringIO, then emits the result.

## Verwandt

- `[[15-features/system/permissions|Smart Approval System]]`
- `[[15-features/system/smart-approval|Aux LLM Risk Assessment]]`
- `[[15-features/commands/permissions|/permissions Subcommand]]`
