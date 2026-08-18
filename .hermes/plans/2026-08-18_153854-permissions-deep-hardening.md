# Plan C: Permissions Deep-Hardening (Hermes-Verbatim Audit)

> **Status:** DRAFT — wartet auf User-Freigabe
> **Auslöser:** User-Audit-08-18-1506 + Hermes `approval.py` Vergleich
> **Priorität:** KRITISCH (Security)

## Diagnose

Hermes' `tools/approval.py` ist **3000+ Zeilen** mit:

- 5 Outcomes: `once / session / always / deny / deny_always / timeout`
- `_redact_sensitive_text` (secrets vor user-display)
- `human_wait_window` ContextVar (exclusion from batch deadline)
- `smart_denied` Mode (Owner-Override: nur once/deny)
- Fail-closed deadlock-guard für prompt_toolkit
- YAML 1.1 `off`-Quirk-Fix

eaccode hat davon ~5%.

## 17 Findings (Hermes-Vergleich)

| # | Hermes-Standard | eaccode-Status | S |
|---|---|---|---|
| C1 | 5 outcomes | Nur `y/n` | HIGH |
| C2 | `timeout` ≠ `deny` | `--` | MED |
| C3 | Secret-Redaction im Prompt | `--` | HIGH |
| C4 | `human_wait_window` | `--` | MED |
| C5 | `smart_denied` Mode | `--` | MED |
| C6 | `allow_permanent=False` (hide always) | `--` | MED |
| C7 | **Deadlock-Guard** (no callback + ptk → fast-deny) | `--` | **HIGH** |
| C8 | YAML 1.1 `off`→False normalize | `--` | LOW |
| C9 | Config-cache (read-only) | `--` | LOW |
| C10 | Unknown-mode → log+fallback | raises | LOW |
| C11 | `_save_blocked_payload` (persistent deny) | `--` | HIGH |
| C12 | `_match_user_deny_rule` | ok | LOW |
| C13 | `_normalize_command_for_detection` | `--` | MED |
| C14 | Path-fold `~` rewrite | `--` | LOW |
| C15 | Exit-code hooks (warnings) | `--` | LOW |
| **B1** | **Inline-Prompt-UX** (y/n clear + echo) | fehlt | **HIGH** |
| B2 | Sensitive-Regex `.env.local` | partial | MED |
| B3 | Path-Symlink-Schutz (`..` traversal) | `--` | MED |

## Was gefixt wird (in dieser Phase)

### Phase C.1 — 5 Outcomes (`once / session / always / deny / deny_always / timeout`)

`PermissionManager.check()` returns more than `Decision(allow, reason)`. Stattdessen:

```python
@dataclass
class Decision:
    outcome: str  # "allow" | "deny" | "timeout"
    reason: str
    mode: str
    duration: str = ""  # "once" | "session" | "always" - only if outcome="allow"
    smart_reviewed: bool = False
```

`ask_handler` returns:

```python
("once", True) | ("session", True) | ("always", True) | ("deny", False) | ("deny_always", False)
```

Plus threading-interne `timeout`-Outcome wenn User nicht antwortet.

### Phase C.2 — Secret-Redaction

`src/eaccode/redact.py` NEU (Hermes-Pattern):

```python
class Redactor:
    def redact(self, text: str) -> str:
        # Mask $-prefixed env vars, AWS keys, JWT, GitHub tokens, ...
        return text_with_masks
```

`display_command = redactor.redact(command)` vor user-display.

### Phase C.3 — Human-wait-window ContextVar

```python
@contextmanager
def human_wait_window():
    token = set_in_batch_deadline(False)
    try:
        yield
    finally:
        reset_in_batch_deadline(token)
```

Permission-Prompts blocked nicht die batch-deadline.

### Phase C.4 — Smart-Denied-Mode (Owner-Override)

`smart_reviewer` returns 4 statt 3:

- `approve`
- `deny`
- `escalate`
- `owner_override` (mit `reason` der vom Aux-LLM kam)

Bei `owner_override`:
- Nur `once` oder `deny` zur Auswahl (kein permanent allow)
- Header: "⚠ AUX LLM BLOCKED, OVERRIDE COMING"

### Phase C.5 — Fail-Closed Deadlock-Guard

```python
def _check_prompt_toolkit_active() -> bool:
    try:
        from prompt_toolkit.application.current import get_app_or_none
        return get_app_or_none() is not None
    except Exception:
        return False

def check(...):
    if self.mode == "smart" and tool_name == "run_command":
        ... # aux review
        # AFTER decision: if smart denied + no ask_handler + ptk active:
        #   raise rather than hang on invisible input()
```

### Phase C.6 — Inline-Prompt-UX (B1)

REPL zeigt **deutlich**:

```
─── Permission needed ─────────────────────────────────
  run_command: chmod 777 /etc/passwd
  Detail: chmod 777 (world-writable)
────────────────────────────────────────────────────────
Choose action:
  [y] once          — approve this call only
  [s] session       — approve all calls of this tool in this session
  [a] always        — approve every chmod 777 globally
  [n] deny
  [A] deny always   — deny every chmod 777 globally

(y/n/s/a/A) ?
```

Plus:
- Echo of pressed key appears (`y ✓`)
- Color-coded (red=y/n, green=yes, yellow=session)

### Phase C.7 — Sensitive-Path-Symlink-Schutz

```python
def _path_normalized(self, path: str) -> str:
    """Resolve .., ~ and symlinks for sensitive-path check."""
    try:
        return str(Path(path).resolve())
    except Exception:
        return path
```

Vor Sensitive-Check.

### Phase C.8 — Blocking-Payload-Denied-Persist

`src/eaccode/permissions_blocked.json`:

```json
{
  "version": 1,
  "blocked_patterns": [
    {
      "pattern": "rm -rf ~/*",
      "added": "2026-08-18",
      "reason": "destructive-recursive-home"
    }
  ]
}
```

`deny_always` schreibt hier. `_match_user_deny_rule()` liest hier.

### Phase C.9 — Exit-Code-Warning-Hook

Wenn `run_command` exit != 0 zurückgibt, **nicht silent**:
- Output enthält `(exit N)` (schon da)
- Plus: nach Tool-Result wrapper: wenn exit != 0, **Statuszeile** mit gelbem Warning

## Inventur

- 8 Phasen, ~12-18 Commits
- 4-5 Dateien geändert, 3-4 NEU
- ~60+ Tests
- ~1500-2000 Zeilen Code

## Was im Scope ist

- Hermes-Verbatim für die Top-7 Findings (C1-C7, B1, B3)
- Output-Reorganization im REPL für `y/n/s/a/A` UX

## Was OUT of Scope ist

- ACP-Bridge (Hermes-only, eaccode hat keine ACP)
- i18n / UI-Language
- Custom Yaml-Validators (PyYAML-default)
- `HERMES_SPINNER_PAUSE` env-var (irrelevant)

## 6 Fragen

1. Plan C freigegeben?
2. 5 outcomes oder simpler mit `(once/session/always)` als 3 + (`deny/deny_always`) als 2-States?
3. Config-File-Persist für `deny_always` (in `~/.local/share/eaccode/blocked.json`)?
4. Redaction: alle sensitive patterns oder nur off-by-default + opt-in?
5. Inline-Prompt-UX: komplette Hermes-5-Option-UI oder simpler `[y/s/a/n]`?
6. Symlink-Schutz: Path.resolve() aggressiv (alle) oder nur für sensitive-targets?
