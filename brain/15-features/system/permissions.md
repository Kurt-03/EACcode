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

## Verwandt

- `brain/15-features/system/agents.md` — Agent-Loop mit Permission-Gate
- `brain/15-features/system/smart_approval.md` — Aux-LLM-Doku (TODO)
- `brain/15-features/system/providers.md` — Provider-Architektur
- Plan: `.hermes/plans/2026-08-18_071745-smart-approval-mode.md`
