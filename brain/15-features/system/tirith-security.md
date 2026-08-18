---
name: tirith-security
type: system
status: done
phase: 08-18 plan-d-h1
date: 2026-08-18
tags: [type/feature, feature/system, security, hermes]
---

# Tirith Security Scanner (H1, Hermes-Verbatim)

> External-binary wrapper for `sheeki03/tirith` v0.3.3 with SHA-256 + Cosign verification.

## Zweck

`tirith` ist ein in Go geschriebener Security-Scanner, der Befehle auf gefährliche
Muster prüft (HIGH/MEDIUM/LOW Findings, JSON-Output). eaccode lädt das Binary
bei erstem Bedarf in `~/.local/share/eaccode/bin/` und ruft es via
`subprocess.run` auf. Das hält den Python-Code schlank und holt die
Erkennungs-Logik aus dem ständig aktualisierten Upstream-Repo.

## Output-Format

```json
{
  "action": "allow | warn | block",
  "findings": [
    {"severity": "HIGH|MEDIUM|LOW", "title": "...",
     "description": "...", "remediation_hint": "..."}
  ],
  "summary": "..."
}
```

## Fail-Mode

- Default (`security.tirith_fail_open: true`): Netzwerk-/Binary-Fehler → `allow`
- Strict (`security.tirith_fail_open: false`): synthetisches `warn` mit
  Finding `tirith-install-error`, der User muss approven

## Verifikation

- **SHA-256** against published `checksums.txt` (mandatory)
- **Cosign**-Verifikation (optional, nur wenn `cosign` auf PATH)

## Plattform-Targets

| OS | Arch | Asset |
|---|---|---|
| Windows | x86_64 | `tirith-x86_64-pc-windows-msvc.zip` |
| macOS | arm64 | `tirith-aarch64-apple-darwin.tar.gz` |
| macOS | x86_64 | `tirith-x86_64-apple-darwin.tar.gz` |
| Linux | aarch64 | `tirith-aarch64-unknown-linux-gnu.tar.gz` |
| Linux | x86_64 | `tirith-x86_64-unknown-linux-gnu.tar.gz` |

## Integration

Wired in `permissions.py:check()` — Layer 6 (Smart-Mode Aux-LLM → Tirith → ask_user).
Wire-Position: NACH aux-LLM-Verdict, VOR ask_handler (in-progress: H22 two-layer).

## Tests

`tests/test_tirith_security.py` — Network-Mock, SHA-Mismatch, Cosign-Pfad, fail-open.

## Verknüpft
[[15-features/system/permissions.md|permissions]] · [[15-features/system/permissions.md|permissions]]

Plan: `.hermes/plans/2026-08-18_170452-hermes-safety-hardening.md`
Hermes source: `_ref/hermes/tools/tirith_security.py` (872 lines)

## Code-Graph (generiert)

- `src/eaccode/tirith_security.py` → [[15-features/system/config.md|config.yaml]]

