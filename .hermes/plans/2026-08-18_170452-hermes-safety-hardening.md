# Plan D: Hermes-Sicherheits-Hardening (Verbatim Audit-Aufarbeitung)

> **Status:** DRAFT — wartet auf User-Freigabe
> **Auslöser:** Audit-Diff zeigt 16% Hermes-Coverage (1343/8137 LOC); 20+ Sicherheits-Features fehlen
> **Priorität:** KRITISCH (mehrere Sicherheits-Lücken)

## Diagnose

User-Prompts (`● echo`, `● del`, `● dir`) halluzinieren **nicht-existente Tools**.
System-Prompt ist zu vage ("Use tools when they help, never invent tool results" — Hermes zeigt **explizit alle Tools** mit Beispiel-Patterns).

**Resultat:** Permissions werden für `echo`/`del`/`dir` aufgerufen, die nicht in eaccode-Tools existieren. Komplette User-Verwirrung.

**Zusätzlich:** Es fehlt ein **Tirith-External-Scanner** (Hermes`go`-binary mit Cosign-Verification) — ein statischer AST-basierter Security-Check der MCommand-Semantik prüft (homograph-URLs, pipe-to-interpreter-Args, terminal-injection). Aktuell nur Regex-Patterns.

## 16 Hermes-Features die fehlen — in 4 Phasen gruppiert

### Phase 1 — Sudo/Parser-Limit/Pattern-Versionierung (1 Tag)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| 7 | `_check_sudo_stdin_guard` — separate Hardline für `sudo -S`/`--stdin` | XS | KRITISCH |
| 6 | `_command_parser_limit_exceeded` — bei Parser-Limit (komplexe Commands) ⇒ Risk | S | HOCH |
| 9 | shlex-Depth-Limit im Detection-Module | S | HOCH |
| 4 | `_normalize_command_for_detection` — String-Cleanup (whitespace, quotes) | XS | MITTEL |
| 5 | `_home_prefix_fold_regex` + `_rewrite_resolved_user_home` — `~`-Pfad-Folding | XS | HOCH |
| 8 | `_legacy_pattern_key` + `_approval_key_aliases` — Pattern-Versionierung | XS | LOW |

### Phase 2 — Hardcoded Exact Paths + Sensitive Directories (1-2 Tage)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| 2 | `file_safety.py` Modul — hardcoded exact sensitive paths + write_denied_prefixes | M | KRITISCH |
| 14 | exakte Pfade: `~/.ssh/{authorized_keys,id_rsa,id_ed25519,config}`, `~/.anthropic_oauth.json`, `~/.netrc`, `~/.pgpass`, `~/.npmrc`, `~/.pypirc`, `~/.git-credentials`, `/etc/sudoers`, `/etc/passwd`, `/etc/shadow` | (Teil von 2) | KRITISCH |
| 15 | sensitive directory prefixes: `~/.ssh`, `~/.aws`, `~/.gnupg`, `~/.kube`, `~/.docker`, `~/.azure`, `~/.config/{gh,gcloud}`, `/etc/sudoers.d`, `/etc/systemd` | (Teil von 2) | KRITISCH |
| 16 | `HERMES_WRITE_SAFE_ROOT` env-var für Whitelist erlaubter Schreib-Pfade | S | MITTEL |
| 17 | classification categories: cross-profile, sandbox-mirror, container-mirror | M | MITTEL |
| 18 | symmetrisches `get_read_block_error` — manche Files dürfen nicht gelesen werden | XS | MITTEL |
| 19 | `raise_if_read_blocked` exception-throwing Variante | XS | LOW |

### Phase 3 — Tirith External Scanner (2-3 Tage)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| 1 | `tirith_security.py` — `tirith` go-binary-Wrapper, Cosign-verified | L | HOCH |
| 11 | `_prepare_smart_approval_observer` — pre-decision observability hooks | M | MITTEL |
| 22 | Two-Layer Pre-Exec-Guard: Tirith AST + dangerous-pattern → kombinierte approval request | M | HOCH |
| 30 | Aux-LLM Findings-Synthese mit `severity`/`finding_id`/`description`/`remediation_hint` | M | HOCH |

### Phase 4 — Cron/Gateway + Container + Misc (2-3 Tage)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| 13 | `_is_cron_approval_context` + `_is_gateway_approval_context` — Context-spezifische Modi | M | HOCH |
| 20 | Cron-approval-mode in config.yaml: `approvals.cron_mode: deny \| approve` | S | HOCH |
| 21 | `approve_known_safe_set` — Liste always-safe Commands | S | MITTEL |
| 3 | `_save_blocked_payload` — parser-limit-blockierte Commands als Script-File speichern | M | LOW |
| 10 | `_format_tirith_description` — formatiert Tirith-Findings als lesbare Tool-Desc | XS | MITTEL |
| 12 | `set_hermes_interactive_context` — interactive vs non-interactive Context | S | MITTEL |
| 23 | Container-Sandbox-Erkennung (`_should_skip_container_guards`) | M | MITTEL |
| 24 | `_YOLO_MODE_FROZEN` — frozen at import-time | XS | HOCH |
| 25 | `_command_matches_permanent_allowlist` — separate Liste von permanent-allow Patterns | S | MITTEL |
| 26 | `is_approval_bypass_active_for_session` — session-spezifische bypass | M | MITTEL |
| 27-29 | Curator (Skill-Lifecycle-Review) | L | OUT-OF-SCOPE |

## Was hinzukommt — Struktur

### Phase 1 — `src/eaccode/sudo_guard.py` NEU + `parser_limit.py` NEU

```python
# src/eaccode/sudo_guard.py
SUDO_STDIN_PATTERNS = (
    r"\bsudo\s+(?!-S|-A|--stdin|--askpass)[^\n]*\b",
    r"\bsudo\s+-S\b",
    r"\bsudo\s+-A\b",
    r"\bsudo\s+--stdin\b",
    r"\bsudo\s+--askpass\b",
    r"\becho\s+.*\s*|\s*sudo\s+-S\b",
)
COMMAND_PARSER_LIMIT = 2048  # chars

def is_sudo_stdin_guess(command: str) -> tuple[bool, str]:
    """Return (True, description) when the command pipes a password to sudo."""
    # matches r'\bsudo\s+(?!-S|-A|--stdin|--askpass).*' SANS -S etc.
    # matches r'\bsudo\s+-S\b'
    # matches r'\becho\s+.*\s*|\s*sudo\s+-S\b' for password-injection
    # matches r'\b(password|passwd|pwd)\b.*sudo.*-S' for password-via-stdin
```

### Phase 2 — `src/eaccode/file_safety.py` NEU

```python
# src/eaccode/file_safety.py — Hermesische hardcoded paths
from pathlib import Path

def build_write_denied_paths(home: Path) -> set[str]:
    """Exact sensitive paths that must NEVER be written."""
    return {
        home / ".ssh" / "authorized_keys",
        home / ".ssh" / "id_rsa",
        home / ".ssh" / "id_ed25519",
        home / ".ssh" / "config",
        home / ".env",
        Path.cwd() / ".env",        # Top-level .env in cwd
        home / ".anthropic_oauth.json",
        Path.cwd() / ".anthropic_oauth.json",
        home / "cache" / "bws_cache.enc.json",
        Path("/etc/sudoers"),
        Path("/etc/passwd"),
        Path("/etc/shadow"),
        home / ".netrc",
        home / ".pgpass",
        home / ".npmrc",
        home / ".pypirc",
        home / ".git-credentials",
    } | {p.resolve() for p in {
        # Some Windows paths too
        Path("/etc/passwd"),  # Unix only — Windows equivalent
    }}

def build_write_denied_prefixes(home: Path) -> list[str]:
    """Sensitive directory prefixes."""
    return [
        home / ".ssh",
        home / ".aws",
        home / ".gnupg",
        home / ".kube",
        home / ".docker",
        home / ".azure",
        home / ".config" / "gh",
        home / ".config" / "gcloud",
        Path("/etc/sudoers.d"),
        Path("/etc/systemd"),
    ]

def is_write_denied(path: str) -> bool:
    """True if path is a denied exact-match or under a denied prefix."""
    resolved = Path(path).resolve()
    home = Path.home()
    exact = build_write_denied_paths(home)
    if resolved in exact:
        return True
    prefixes = build_write_denied_prefixes(home)
    return any(str(resolved).startswith(str(p)) for p in prefixes)
```

### Phase 3 — `src/eaccode/tirith_security.py` NEU

```python
# src/eaccode/tirith_security.py — External Security Scanner Wrapper
class TirithResult:
    action: str  # "allow" | "warn" | "block"
    findings: list  # [{"severity": "HIGH", "title": ..., "description": ..., "remediation_hint": ...}]
    summary: str

def check_command_security(command: str) -> TirithResult:
    """Call the external tirith binary, parse JSON output.
    
    Falls back to {"action": "allow"} if tirith is not installed AND
    security.tirith_fail_open is True. If tirith is missing AND
    fail_open is False, returns {"action": "warn"} with finding
    'tirith-import-error'.
    """
```

**Realität:** eaccode's `tirith` ist nicht ausführbar (Go-Binary). Lösung: **Embed simplified Ruby/Python-based rules** in eaccode selbst — keine externe Binary, ABER identische Rules. Ich nenne es `smart_security.py` (kein tirith-binary, sondern inline AST-checks).

### Phase 4 — `src/eaccode/cron_mode.py` NEU

```python
# src/eaccode/cron_mode.py
CRON_MODE_DENY_BLOCK_TEMPLATES = (
    "cron_job_blocked: {description}",
)

def is_cron_context() -> bool:
    """True when running under cron (env var, no tty, ..)."""

def get_cron_approval_mode() -> str:
    """'deny' (default) | 'approve' from config.yaml approvals.cron_mode."""
```

## Update `PermissionManager.check()`

Aktuelle Pipeline wird um **Phase 1 + 2 + 4** Outputs erweitert:

```python
def check(self, tool_name, arguments):
    call = self.call_text(tool_name, arguments)
    
    # Phase 2: hardcoded exact paths (Phase 2)
    if tool_name in ("write_file", "patch_file", "file_edit"):
        path_arg = self._extract_path_arg(tool_name, arguments)
        if path_arg and is_write_denied(path_arg):
            return self._ask_user(tool_name, arguments, 
                                   fallback_reason="hardcoded sensitive path (file_safety)",
                                   sensitive=True)
    
    # Phase 1: sudo-stdin-guard (Phase 1) — vor hardline
    if tool_name == "run_command":
        command = arguments.get("command", "")
        is_sudo, sudo_desc = is_sudo_stdin_guess(command)
        if is_sudo:
            return Decision(False, f"sudo-stdin blocked: {sudo_desc}", self.mode)
        
        # Phase 1: parser-limit (Phase 1)
        if len(command) > COMMAND_PARSER_LIMIT:
            return _save_blocked_payload_or_deny(command, ...)
        
        # Phase 1: home-fold (Phase 1)
        normalized = normalize_command_for_detection(command)
        is_hardline, desc = detect_hardline_command(normalized)
        if is_hardline:
            return ...
```

## Was die Implementierung in commits ergibt

**12-18 Commits** über 7-10 Arbeitstage (User-Fokus):
1. `feat(safety): add sudo-stdin-guard (H7)`
2. `feat(safety): command-parser-limit (H6)`
3. `feat(safety): normalize-command + home-fold (H4, H5)`
4. `feat(safety): pattern-key-versioning (H8)`
5. `feat(file_safety): hardcoded paths + denied-prefixes (H2, H14, H15)`
6. `feat(file_safety): HERMES_WRITE_SAFE_ROOT env-var (H16)`
7. `feat(file_safety): classification categories (H17)`
8. `feat(file_safety): read-blocked + raise-variants (H18, H19)`
9. `feat(tirith-security): smart_security.py inline AST-checks (H3, H30)`
10. `feat(approvals): two-layer pre-exec-guards (H22)`
11. `feat(approvals): cron-mode config + gateway-context (H13, H20)`
12. `feat(approvals): container-sandbox-detection (H23)`
13. `feat(approvals): yolo-mode-frozen (H24)`
14. `feat(approvals): known-safe-set + allowlist-separate (H21, H25)`
15. `feat(approvals): session-bypass (H26)`
16. `feat(approvals): interactive-context + format-description (H10, H12)`
17. `feat(approvals): observer hooks (H11)`
18. `feat(approvals): save-blocked-payload (H3)`

Plus:
- Brain-Updates in `brain/15-features/system/permissions.md`, `file_safety.md`, `cron-mode.md`, `smart-security.md` (NEU)
- Test-Suite von 50+ neuen Tests
- ADR-0007 "Hermes-Sicherheits-Hardening" mit Verweis auf alle 18 Items

## Was bewusst OUT-OF-SCOPE ist (Nice-to-have)

| # | Hermes-Feature | Grund |
|---|---|---|
| 11 | Observer-Hooks für SDK-Consumer | Kein SDK vorhanden |
| 27-29 | Curator (Skill-Lifecycle-Review) | B5 ist dein OK aber Curator ist eine gesamte Subkomponente (2000 LoC) — separate Phase |
| 3 | `_save_blocked_payload` Block-Script-Save | Nice to have, brauchen wir nicht wenn Parser-Limit sauber ist |

## 4 Fragen

1. Plan D freigegeben?
2. Soll ich alle 4 Phasen sofort machen, oder in 4 Iterationen (je 2-3 Tage)?
3. `tirith_security.py` als Vereinfachung (Python-only, keine Go-binary) oder das echte Tirith aufsetzen?
4. Brain-Doku für alle 4 neuen Module gleich mit-aktualisieren, oder nur permissions.md zentral?

## Tests (pro Phase erwartet)

| Phase | Tests | Files |
|---|---|---|
| Phase 1 | 25 | tests/test_sudo_guard.py, tests/test_parser_limit.py, tests/test_normalize.py, tests/test_path_fold.py, tests/test_pattern_version.py |
| Phase 2 | 30 | tests/test_file_safety.py, tests/test_safe_roots.py, tests/test_read_blocked.py, tests/test_safety_classification.py |
| Phase 3 | 20 | tests/test_smart_security.py |
| Phase 4 | 40 | tests/test_cron_mode.py, tests/test_yolo_mode.py, tests/test_container_safety.py, tests/test_known_safe.py, tests/test_allowlist.py, tests/test_bypass.py, tests/test_observer.py |

**Total: ~115 neue Tests** → eaccode von 641 → ~750 Tests grün.

## Live-Verifikation

Nach Phase 2 muss das Test:
```
$ eaccode -p "ls ~/"
[früher: Permission-Prompt]
[nachher: read-only auto-approve]

$ eaccode -p "echo 'exec' >> ~/.ssh/authorized_keys"
[früher: Permission-Prompt mit "Action: shell command"]
[nachher: BLOCKED: write_denied_paths blockiert ~/.ssh/authorized_keys]

$ eaccode -p "sudo cat /etc/shadow"
[früher: hardline block]
[nachher: Sudo-Stdin Guard + Hardline block vor Hardline]

$ eaccode -p "echo 'x' | sudo -S"
[früher: 'none' danger pattern matched nicht]
[nachher: sudo_stdin_guard blockiert via 'echo | sudo -S pattern']
```
