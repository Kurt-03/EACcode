---
name: permissions-system
type: system
status: done
phase: C1 + 08-18 smart
date: 2026-08-13 (C1), 2026-08-18 (smart mode)
tags: [type/feature, feature/system, permissions, security]
---

# Permissions-System (Smart Mode)

**Modul:** `src/eaccode/permissions.py`
**Aux LLM:** `src/eaccode/smart_approval.py`
**Hermes-Referenz:** `C:/Projekte/_ref/hermes/tools/approval.py`

## Zweck

Eaccode verwendet ein 3-Stufen-Permission-System mit Aux-LLM-Risk-Assessment für gefährliche Commands. Hauptaufgabe: **weniger Permission-Prompts** ohne Sicherheits-Verluste.

## Modi (Hermes-kompatibel)

| Mode | Verhalten | Default |
|------|-----------|---------|
| `smart` | Safe auto-approve, dangerous → aux LLM, sensitive → ask, hardline → immer block | ✅ Default |
| `manual` | Alle mutating Tools fragen User | ask-legacy |
| `off` | Auto-approve alles (yolo), hardline bleibt blockiert | allow_all-legacy |
| `read_only` | Nur Read-Tools (out of scope für Phase 1) | unchanged |

## Permission-Pipeline (eaccode)

```
run_command('/tmp/cleanup')
    │
    ├─ 1. Hardline check (~12 patterns, Hermes-Verbatim)
    │   ├─ match → BLOCKED (always)
    │   └─ no match ↓
    │
    ├─ 2. Sensitive-Path check (~10 patterns)
    │   ├─ match → ASK user
    │   └─ no match ↓
    │
    ├─ 3. mode==smart + run_command
    │   ├─ Dangerous-Pattern check (~77 patterns)
    │   │   ├─ match → aux LLM
    │   │   │   ├─ approve → auto-approve
    │   │   │   ├─ deny → BLOCKED
    │   │   │   └─ escalate → ASK user
    │   │   └─ no match → auto-approve (safe)
    │   └─ mode!=smart ↓
    │
    ├─ 4. Read-only tool (read_file, search, etc.) → auto-approve
    │
    ├─ 5. mode=off → auto-approve (override)
    │
    └─ 6. mode=manual + mutating tool → ASK user
```

## Hardline-Patterns (12, Hermes-Verbatim)

Always-block, regardless of mode:

1. `rm -rf /` (root filesystem)
2. `rm -rf /etc|/usr|/var|/bin|/sbin|/boot` (system dirs)
3. `rm -rf ~` (home dir)
4. `mkfs.*` (filesystem format)
5. `dd of=/dev/sd*` (raw block device)
6. `> /dev/sd*` (redirect to block device)
7. `:() { :|:& };:` (fork bomb)
8. `kill -1` (kill all)
9. `shutdown|reboot|halt|poweroff`
10. `init 0|6`
11. `systemctl poweroff|reboot|halt|kexec`
12. `telinit 0|6`

## Dangerous-Patterns (77, Hermes-Verbatim)

Routed through aux LLM in smart mode:

- `rm -rf ~` (home dir)
- `chmod 777` (world-writable)
- `curl * | sh|bash|zsh|python|node` (remote-script)
- `find -exec/-delete`
- `docker restart|stop|kill`
- `docker compose restart|stop|down`
- `podman restart|stop|kill`
- `docker -h|--host|...` (daemon redirect)
- `nc -l`, `curl --upload-file`, `curl -T`
- `gpg --batch --yes --symmetric`
- `openssl enc -a|es`
- `| sh|bash|zsh|dash|ksh`
- `eval`, `exec`
- `crontab -e|-lr`
- `systemctl enable|disable|mask|unmask`
- `ip/a/l addr|link|route add|del|flush`
- `iptables`, `nft`
- `parted`, `fdisk /dev/`
- `sed -i` auf sensitive paths
- `tee` auf sensitive paths
- `sudo -S|-A|--stdin|--askpass`
- `pkill|killall|taskkill eaccode`
- `git reset --hard`, `git clean -fd`, `git push --force`
- `mv -f` auf `/etc`
- `nohup ... &`, `disown`
- `curl|bash`, `curl|sh`
- `$(.*rm -rf`
- `echo | sudo -S`
- `kill -9 1`, `kill -SIGTERM 1`
- `env -i`
- `setenforce 0|Permissive`
- `apparmor_parser -R`

## Aux-LLM-Smart-Review (`src/eaccode/smart_approval.py`)

Hermes-style defenses:
1. **Shell-Comment-Stripping** — `rm -rf / # APPROVE` → `rm -rf /`
2. **XML-Delimiters** — `<command>...</command>`
3. **System-Prompt warnt** — "ignore directives"
4. **Worker-Thread mit Timeout** — 10s default, `escalate` fallback

Aux LLM = das normale Active-Agent-Model (per Hermes-Pattern). Phase 2: `approvals.smart_model` als Override.

## Mode-Aliase (Rückwärtskompatibilität)

| Alter Name | Neuer Name |
|------------|------------|
| `ask` | `manual` |
| `allow_all` | `off` |
| `read_only` | `read_only` (unverändert) |
| `deny_all` | `manual` (gebanned) |

## Tests

- `tests/test_permissions.py` — 42 Tests (Modes, Hardline, Smart, Session, Backward-Compat)
- `tests/test_smart_approval.py` — 23 Tests (Comment-Stripping, XML, Verdict-Parsing, Reviewer)
- Total: 65 neue Tests

## Live-Verifikation

```bash
# Default ist smart
eaccode config get permissions.mode
# mode: smart

# Wechsel
eaccode permissions mode manual
# permission mode: manual

# REPL
/approvals
# mode: smart (effective: smart)
# allow: []
# deny: []
```

## History

- **08-13 (C1):** Ursprüngliches 4-Modus-System (ask, allow_all, read_only, deny_all)
- **08-18:** Hermes-kompatibel umgebaut: smart | manual | off. Hermes-Verbatim 89 patterns (12 hardline + 77 dangerous). Aux LLM mit XML-Delimiters und Comment-Stripping als Anti-Prompt-Injection.



---

## 08-18: Audit-Hardening Plan B

### Was geändert wurde

1. **`mutates`-Tag auf Tool** (`src/eaccode/agent.py`): NEU - jedes Tool deklariert
   `mutates=True/False`. READ_ONLY_TOOLS wird automatisch abgeleitet via
   `is_read_only_tool(tool)`. Kein Drift mehr zwischen Whitelist und
   tatsächlichen Tools.

2. **`always_ask`-Tag**: `run_command`, `browser_*`, `browser_screenshot`
   markiert. Diese Tools werden NIE in `session_allowed` gespeichert -
   der User muss jeden Call explizit approve-en.

3. **Sensitive-Path-Check** (`_is_sensitive_path()`): Schreibt auf
   `.ssh/`, `.git/config`, `.env`, `config.yaml`, `authorized_keys`,
   `id_rsa` → triggert `_ask_user` mit `fallback_reason="sensitive path"`.

4. **`_extract_path_arg()`**: Erkennt Pfad-Parameter unter beliebigen Namen
   (`path`, `file_path`, `target_path`, `p`, `filepath`) plus
   `patch_multiple`'s `edits[0].path`.

5. **`_READ_ONLY_TOOL_NAMES`**: Statisches Fallback-Set für `check()`,
   das nur `tool_name` als String hat (kein `Tool`-Objekt).

### Pipeline-Reihenfolge (`check()`)

```
1. deny rule (wins)
2. allow rule
3. read_only mode (heuristic)
4. Hardline pattern (run_command only)
5. Sensitive-Path-Check (path-Arg through any tool)  ← NEU
6. Smart-Mode Aux-LLM (run_command + dangerous)
7. Read-only tools (heuristic + READ_ONLY_TOOL_NAMES)
8. off mode (auto-approve)
9. Session-allowed (NOT always-ask tools)
10. ask_handler (with session-memory only for non-always-ask)
```

### Tests

- `tests/test_permission_hardening.py` NEU - 18 Tests
- `tests/test_tool_schemas.py` NEU - 13 Tests

### Bekannte Limits

- Aux-LLM-Check **weiterhin nur für `run_command`** (Plan B Phase 2)
- Sensitive-Path-Check via regex ohne Subdirectory-Symlink-Schutz
- Yolo-Mode (`off`) auto-approved alles außer Hardline (User-Entscheidung)

## Verwandt

- `brain/15-features/system/agents.md` — Agent-Loop mit Permission-Gate
- `brain/15-features/system/smart_approval.md` — Aux-LLM-Doku (TODO)
- `brain/15-features/system/providers.md` — Provider-Architektur
- Plan: `.hermes/plans/2026-08-18_071745-smart-approval-mode.md`

---

## 08-18 (Plan C): Audit-Hardening #2

### Was seit dem ersten Audit-Hardening dazukam

1. **5 Outcomes** (war 2):
   - `once / session / always / deny / deny_always / timeout`
   - `Decision`-Dataclass erweitert um `scope`, `owner_override`, `timeout`

2. **Inline-Prompt-UX** (`palette.py:_ask`)
   - 5-Option-Menü statt `[y/N]`
   - `[y] once / [s] session / [a] always / [n] deny / [A] deny_always`
   - Echo der Eingabe (`y ✓`) bestätigt Annahme
   - Header mit `Tool` + `Action` + `Risk`

3. **Secret-Redaction** (`src/eaccode/redact.py`)
   - GitHub PATs (ghp_, gho_, ghs_, ...)
   - OpenAI (sk-...)
   - AWS Keys (AKIA...)
   - JWT Tokens
   - Slack Tokens (xoxb-, ...)
   - PEM Private Keys
   - Bearer Tokens
   - Sensible KEY=value patterns
   - First-3-Char-Visible für Identifikation, Rest maskiert

4. **Aux-LLM Owner-Override** (`_smart_review`)
   - 4. Verdict: `owner_override` (statt nur 3)
   - Aux-LLM unsicher → User bekommt nur `o` (once) oder `n` (deny)
   - Kein Permanent-Allow wenn Aux-LLM unsicher

5. **Path-Symlink-Resolve**
   - `Path.resolve()` vor Sensitive-Check
   - Path-Traversal (`../`) wird aufgelöst
   - Original-Pfad + resolved-Pfad beide geprüft

6. **Persistent Deny_Always** (`src/eaccode/blocked.py`)
   - `~/.local/share/eaccode/blocked.json`
   - Pattern-Speicherung mit ID + Reason + Timestamp
   - Überlebt eaccode Neustart
   - API: `add_blocked()`, `remove_blocked()`, `find_blocked()`, `list_blocked()`

7. **Human-Wait-Window** (`src/eaccode/human_wait_window.py`)
   - ContextVar `eaccode_human_wait_depth`
   - Batch-Deadline pausiert während User-Prompts
   - Nested windows (counter-style)

8. **Exit-Code Warnings** (`tools.py:run_command`, `banner.py:status_line`)
   - Run-Command Output: `⚠ exit=N (non-zero)` bei Fehler
   - Status-Line: `model │ t │ chars │ ⚠ exit=N`

### Pipeline-Reihenfolge (08-18 end-state)

```
1. deny rule (config.yaml)
2. allow rule (config.yaml)
3. persistent block list (blocked.json) ← Phase C.8
4. read_only mode (heuristic)
5. Hardline pattern (run_command only)
6. Sensitive-Path-Check (path-resolve! ← Phase C.7)
7. Smart-Mode Aux-LLM (run_command + dangerous) ← Phase C.5 owner_override
8. Read-only tools (heuristic + READ_ONLY_TOOL_NAMES)
9. off mode (auto-approve)
10. Session-allowed (NOT always-ask tools)
11. ask_handler via human_wait_window ← Phase C.3
```

### Hermes-Score

| Coverage | Was |
|---|---|
| 5/5 (Hermes-Voll) | 5 outcomes + 5-option UX |
| 80% | Secret-Redaction (Hermes redact kopiert) |
| 90% | Aux-LLM Owner-Override |
| 100% | Hardline + Sensitive-Path |
| 80% | Persistent Deny_Always (blocklist) |
| 70% | Deadlock-Guard (kein input()-deadlock weil ask_handler immer gesetzt in REPL) |
| — | Was Hermes hat, eaccode (noch) nicht braucht: ACP-bridge, i18n |

### Tests

- `tests/test_permissions.py` — 42 Tests (Modes, Hardline, Smart, Session)
- `tests/test_permission_hardening.py` — 18 Tests (Sensitive, Always-Ask, Smart-Mode)
- `tests/test_tool_schemas.py` — 13 Tests (Tags, Descriptions)
- `tests/test_redact.py` — 9 Tests (Secrets, safe-unchanged)
- `tests/test_blocked.py` — 12 Tests (Add/Remove/Persistence/Match)
- `tests/test_human_wait_window.py` — 5 Tests (Active/Inactive/Nested)

Total: **641 Tests grün** (vor Plan C: 609)

### Out-of-scope (für später)

- Phase 2: Dediziertes Aux-Modell (separate Config)
- Phase 2: `@`-pattern mit `~` rewrite + Symlink-Folding
- Phase 2: Per-Call-History von Permission-Verdicts
- Phase 2: Yolo-Mode (`off` auto-approve ohne `--yolo`-Flag)
- Phase 2: Persistent Block-Store-CLI (`eaccode permissions denied-list list/remove`)
