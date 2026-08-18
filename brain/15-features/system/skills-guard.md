---
name: skills-guard
type: system
status: done
phase: 08-18 plan-g-v5-g9
date: 2026-08-18
tags: [type/feature, feature/system, security, hermes]
---

# Skill AST Audit (G.9)

> Scannt Skills vor `install` auf Prompt-Injection, Exfiltration-Hints und
> destructive Code. Content-Hash-Cache verhindert Re-Scan bei unveränderten
> Skills.

## Detection-Patterns

| Category | Beispiel | Severity |
|---|---|---|
| **Prompt-Injection** | "ignore prior directives", "disregard previous context" | HIGH |
| **Exfiltration** | `curl POST`, DNS-exfil, env-var-leakage | HIGH |
| **Destructive** | `rm -rf`, `dd`, `mkfs`, `format C:`-style | HIGH |
| **Suspicious-Tools** | Shell mit `eval`/`exec`, base64-decoded pipe | MEDIUM |
| **Style-Warnings** | Encoded payloads, suspicious unicode | LOW |

## API

```python
@dataclass
class Finding:
    rule_id: str
    severity: str   # HIGH | MEDIUM | LOW
    title: str
    description: str
    def to_dict() -> dict

SEVERITY_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

def scan_skill(skill_dir: Path) -> list[Finding]
def is_clean(findings: list[Finding]) -> bool   # no HIGH/MEDIUM
```

## Cache

```python
def _content_hash(skill_dir) -> str
def scan_skill_cached(skill_dir) -> list[Finding] | None
```

Cache-Key = `sha256(skill_dir/SKILL.md + body + frontmatter)`. Wenn gleicher
Hash im Cache → skip. Tests löschen via `clear_cache()`.

## Wire-Position

`/skill install` ruft `scan_skill_cached()` *vor* Persist. Bei HIGH-Finding:
Hard-Block; MEDIUM: ASK; LOW: Log-only.

## Verknüpft

- [[15-features/system/tool-architecture.md|tool-architecture]] · G.9
- [[15-features/system/skill-system.md|skill-system]]
- Hermes source: `_ref/hermes/tools/skills_guard.py:scan_skill`

## Tests

`tests/test_skills_guard.py` — Clean-skill pass, synthetic malicious-skill
high-finding, cache hit/miss/invalidate, hash determinism.
