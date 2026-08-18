---
name: clarify-tool
type: system
status: done
phase: 08-18 plan-g-v5-g4
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# Clarify Tool (G.4)

> Modell fragt User via Multiple-Choice statt zu halluzinieren. Integriert mit
> eaccode-UX (Palette-Pattern, single/multi-select).

## Zweck

Wenn das Modell an einer Ambiguität hängenbleibt (z. B. „Welcher Branch?"),
kann es `clarify(question, choices=[...], multi_select=True/False)` aufrufen.
UX rendert die Auswahl wie `clarify` aus Hermes.

## Public API

```python
@dataclass
class ClarifyChoice:
    label: str
    description: str = ""

@dataclass
class ClarifyResult:
    selected: list[str]
    multi_select: bool
    raw: str

def invoke_callback(callback, question, choices, multi_select) -> ClarifyResult | None
```

`callback` ist typischerweise `palette._ask_with_choices`. Fallback: stdin-readline
(wenn keine Callback-Registry, z. B. in Tests).

## UX-Integration

In `palette.py`:

```
❯ Was meinst du mit "Branch"?
  ❯ main
    feature/auth
    experimental
    (Andere)
```

Tab/Enter = multi-select, Single-Enter = single-select.

## Tests

`tests/test_clarify_tool.py` — invoke_callback mit Fake-Callback, multi/single,
raw-Pass-Through.

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.4
- [[15-features/system/slash-palette.md|slash-palette]]
- Hermes source: `_ref/hermes/tools/clarify_tool.py`
