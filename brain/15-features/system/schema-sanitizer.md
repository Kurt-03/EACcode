---
name: schema-sanitizer
type: system
status: done
phase: 08-18 plan-g-v5-g5
date: 2026-08-18
tags: [type/feature, feature/system, tools, hermes]
---

# JSON-Schema Sanitizer (G.5)

> Manche Provider (deepseek, kimi, minimax, moonshot) lehnen Schemas mit
> `$ref`, komplexen unions, `const`, oder `format-pattern` ab. Sanitizer
> normalisiert auf eine portable Subset-Form.

## Strict-Provider-Liste

```python
_STRICT_PROVIDERS = {"openai", "deepseek", "xiaomi", "moonshot", "kimi", "minimax"}
```

## Was bereinigt wird

| Pattern | Ersetzt durch |
|---|---|
| Property-Key mit Dots/Spaces | Single underscore (`foo.bar` → `foo_bar`) |
| Numeric Property-Key-Start | Underscore-Prefix (`5foo` → `_5foo`) |
| `$ref` mit Pfad | Inline-resolved |
| `const`-Field | `enum: [const_value]` |
| `nullable: [...]` unions | `type: ["null", ...orig]` |
| `format: "date-time"` etc. | comment-only (`description`: ...) |

## API

```python
def sanitize_property_key(key) -> str
def sanitize_schema(schema, *, provider) -> dict
def is_strict_provider(name) -> bool
```

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.5
- [[15-features/system/providers.md|providers]]
- Hermes source: `_ref/hermes/tools/schema_sanitizer.py`

## Tests

`tests/test_schema_sanitizer.py` — Property-Key sanitize, each-strict-provider
spezifische Fälle, idempotenz (sanitize(sanitize(x)) == sanitize(x)).
