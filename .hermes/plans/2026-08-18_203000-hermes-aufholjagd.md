# Plan H: Aufholjagd zur vollständigen Hermes-Coverage

> **Status:** DRAFT — wartet auf User-Freigabe
> **Auslöser:** User-Anforderung "tiefer audit, was fehlt noch, muss mit rein"
> **Stand:** eaccode-Coverage **4.7%** von Hermes (371 von 7866 Funktionen)

## Ehrlicher Coverage-Stand

```
Hermes-Subsystem       Funktionen   LOC          eaccode-Coverage
agent/                  1795        114,642      ~5% (eaccode: ~90 funcs)
tools/                  2123        112,609      ~7% (eaccode: ~150 funcs)
hermes_cli/             3850        196,942      ~1% (eaccode: ~30 funcs)
acp_adapter/              98          5,809      0%  (komplett fehlt)
─────────────────────────────────────────────────────────────────
TOTAL                   7866        430,002      4.7%
```

**Was wir bisher gemacht haben** (Plan G v5 + v6):
- 13 neue Module für Permissions + Tool-Sicherheit
- Hermes-Coverage für Permissions: ~80%
- Hermes-Coverage für Tool-Architektur: ~30%
- Hermes-Coverage für `hermes_cli/` (alle /commands, UI): ~1%
- Hermes-Coverage für `acp_adapter/` (Remote-Protocol): 0%

## Was noch fehlt — 24 Bereiche

### Block A — Permissions (Plan G v4 nicht-funktionale Reste)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| H1 | **Operator-Policy** (`approvals.smart_policy`) im System-Prompt | XS | HOCH |
| H2 | **Stage-Approval** (memory/skills pending/) mit `/memory pending` + `/skills pending` Slash-Commands | XL | HOCH |
| H3 | **Content-Threat-Scan** (`scan_for_threats(content)`) — Prompt-Injection in tool-output, skill-content, model-response | M | HOCH |
| H4 | **Path-Validation** (`validate_within_dir(path, root)`, `has_traversal_component(path_str)`) | XS | MITTEL |
| H5 | **SSRF-Schutz** (`is_safe_url(url)`, `is_always_blocked_url(url)`, sensitive_query_params, private-IP-blocking) | XL | KRITISCH |
| H6 | **Interpreter-Detection** (`_interpreter_family()`, `_execution_flag_findings()`) — `python -c`, `node -e`, `bash -c` erkennen | XL | KRITISCH |
| H7 | **Shell-Token-Parser** (`_shell_tokens_with_spans()`, `_iter_top_level_shell_segments()`) — AST-like analyse, $(), backticks | XL | HOCH |
| H8 | **Owner-Override UX** wire (`_ask_owner_override` im palette) | S | MITTEL |
| H9 | **Plugin-Observability-Hooks** (`_fire_approval_hook`, `_prepare_smart_approval_observer`, `_observe_smart_approval_verdict`) | M | LOW |
| H10 | **Approval-Persistence-Funktionen** (`approve_session`, `approve_permanent`, `load_permanent`, `_has_allowlist_shell_operator`, `_command_matches_permanent_allowlist`, `load_permanent_allowlist`, `save_permanent_allowlist`) | M | HOCH |
| H11 | **Plugin-Override-Policy** + Toolset-Aliases + Toolset-Checks (`_plugin_override_policy`, `_toolset_checks`, `_toolset_aliases`) | M | MITTEL |

### Block B — Sandbox / Container-Architecture (Hermes `terminal_tool.py` ~3800 LOC)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| H12 | **Docker-Container-Per-Task** (`_create_environment(env_type, image, cwd, timeout)`) — Sandbox für jeden Sub-Agent | XL | KRITISCH |
| H13 | **Task-Env-Overrides** (`register_task_env_overrides(task_id, overrides)`, `clear_task_env_overrides(task_id)`) — per-task images | M | HOCH |
| H14 | **Container-Aliasing** (`register_container_alias(child, parent)`, `_resolve_container_alias(task_id)`) | M | HOCH |
| H15 | **Container-Session-Isolation** (`_docker_session_isolation_enabled()`) — fresh sandbox pro Session | M | HOCH |
| H16 | **Cleanup-Thread** (`_cleanup_thread_worker`, `_cleanup_inactive_envs(lifetime_seconds)`) — auto-cleanup inactive sandboxes | M | HOCH |
| H17 | **Docker-Volume-Host-Path-Detection** (`_docker_volume_uses_host_path`, `_docker_has_host_access`) — Sandbox escape prevention | M | KRITISCH |

### Block C — ACP/Gateway/Remote-Protocol (Hermes `acp_adapter/` 5809 LOC)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| H18 | **ACP-Adapter** (Agent-Communication-Protocol für Remote-Gateway) | XL | KRITISCH für Remote |
| H19 | **Gateway-Approval-Resolver** (`resolve_gateway_approval`, `_await_gateway_decision`) | M | HOCH |
| H20 | **Gateway-Notify-Registration** (`register_gateway_notify`, `unregister_gateway_notify`) | S | MITTEL |
| H21 | **Pending-Approval-Store** (`submit_pending`, `has_blocking_approval`) | M | HOCH |

### Block D — Tool-Auswahl (Plan G v5 nicht-funktionale Reste)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| H22 | **Tool-Search Auto-Activation** (deferred-tool-catalog wird **automatisch** aktiviert wenn context-window tight, nicht nur "wenn Plugin-Tools vorhanden") | M | HOCH |
| H23 | **Plugin-Tools** (`hermes_plugins.X.tool` registration-via-Plugin-Loader) | XL | HOCH |
| H24 | **Coerce-Tool-Args** (`coerce_tool_args(tool_name, args)`) — type-coercion "42" → 42 | M | MITTEL |

### Block E — UX-Features (Hermes `hermes_cli/` 196K LOC!)

| # | Hermes-Feature | Effort | Severity |
|---|---|---|---|
| H25 | **Slash-Commands komplett** — Hermes hat ~3850 Funktionen in hermes_cli, eaccode hat ~30. Massive Lücke. `/help`, `/config`, `/memory`, `/skills`, `/model`, etc. | XL | HOCH |
| H26 | **Banner-Informationen** (System-Probe + Memory-Hint + Skill-Injection) | M | MITTEL |
| H27 | **Output-Renderer** (markdown, syntax-highlight, table-format) | L | MITTEL |

## Priorisierung — Was **muss** rein?

### Tier 1 — Sicherheitskritisch (KRITISCH)

| # | Hermes-Feature | Warum |
|---|---|---|
| **H5** | SSRF-Schutz | `http_get` ist aktuell SSRF-vulnerable |
| **H6** | Interpreter-Detection | `python -c "import os; os.system('rm -rf /')"` wird aktuell nicht erkannt |
| **H7** | Shell-Token-Parser | `$()` substitution, backticks — komplexe Attacks unentdeckt |
| **H12** | Docker-Container-Per-Task | Filesystem-Isolation fehlt komplett |
| **H17** | Docker-Volume-Host-Path-Detection | Sandbox-Escape-Prevention |
| **H18** | ACP-Adapter | Remote-Gateway ohne ACP nicht möglich |

### Tier 2 — Funktions-kritisch (HOCH)

| # | Hermes-Feature | Warum |
|---|---|---|
| **H1** | Operator-Policy | User kann Aux-LLM custom-rules geben |
| **H2** | Stage-Approval (memory/skills pending) | Hermes-Pattern: writes staged, user reviews |
| **H3** | Content-Threat-Scan | Prompt-Injection in tool-output erkennen |
| **H10** | Approval-Persistence-Funktionen | `permissions.allow/deny` config ohne proper Hermes-API |
| **H13** | Task-Env-Overrides | Per-Task container image selection |
| **H14** | Container-Aliasing | Sub-Agents teilen parent's Container |
| **H15** | Container-Session-Isolation | Fresh-Sandbox per Session |
| **H16** | Cleanup-Thread | Sandboxes werden zu alte, cleanup nötig |
| **H19** | Gateway-Approval-Resolver | Remote-decisions empfangen |
| **H21** | Pending-Approval-Store | Async approvals persistieren |
| **H22** | Tool-Search Auto-Activation | Bridge-tools automatisch verfügbar machen |
| **H23** | Plugin-Tools | Plugin-Loader für 3rd-party-Tools |
| **H25** | Slash-Commands komplett | `~3800 hermes_cli` Funktionen vs. `~30 eaccode` |

### Tier 3 — Nice-to-have (MITTEL/LOW)

H4, H8, H9, H11, H20, H24, H26, H27

## Empfehlung

**3 große Sprint-Wellen**, ~3-4 Wochen pro Welle:

### Sprint-Welle 1 (4 Wochen, KRITISCH + HOCH)

```
Woche 1-2:
  H5  SSRF-Schutz                  ~500 LOC
  H6  Interpreter-Detection        ~600 LOC
  H7  Shell-Token-Parser           ~800 LOC
  H1  Operator-Policy              ~100 LOC
  H10 Approval-Persistence-Funcs   ~400 LOC

Woche 3:
  H12 Docker-Container-Per-Task    ~1200 LOC (mit Docker-Integration)
  H17 Docker-Volume-Host-Path      ~300 LOC
  H13 Task-Env-Overrides           ~300 LOC
  H14 Container-Aliasing            ~250 LOC
  H15 Container-Session-Isolation  ~150 LOC
  H16 Cleanup-Thread               ~250 LOC

Woche 4:
  H2  Stage-Approval (memory/skills pending)   ~1000 LOC
  H3  Content-Threat-Scan          ~500 LOC
  H22 Tool-Search Auto-Activation  ~300 LOC
```

**Total:** ~6650 LOC, ~150 Tests

### Sprint-Welle 2 (4 Wochen, ACP + Slash-Commands)

```
Woche 5-6:
  H18 ACP-Adapter                   ~1500 LOC
  H19 Gateway-Approval-Resolver     ~400 LOC
  H20 Gateway-Notify-Registration   ~150 LOC
  H21 Pending-Approval-Store        ~400 LOC
  H23 Plugin-Tools                   ~800 LOC

Woche 7-8:
  H25 Slash-Commands komplett:
    /help + /config + /model + /memory + /skills + /checkpoints
    /auth + /blueprint + /bundle + /approvals + /interrupt
    (jedes Slash-Command = 1 sub-module, ~100-200 LOC)
```

**Total:** ~3250 LOC, ~80 Tests

### Sprint-Welle 3 (2 Wochen, Polish)

```
H4  Path-Validation
H8  Owner-Override UX wire
H9  Plugin-Observability-Hooks
H11 Plugin-Override-Policy
H24 Coerce-Tool-Args
H26 Banner-Informationen
H27 Output-Renderer
```

**Total:** ~1200 LOC, ~50 Tests

## Was das für eaccode bedeutet

**Endstand nach Welle 1+2+3:**
- Hermes-Coverage: 4.7% → **~70%** (wir können nie 100% erreichen — vieles ist Hermes-spezifisch wie Cloud-Gateway, Azure, Discord-Tools, etc.)
- LOC: 12K → ~25K
- Tests: 877 → ~1500 grün

**Was bewusst NICHT rein wird (Hermes-spezifisch, nicht für eaccode):**
- Cloud-Gateway (Nous, Modal, Daytona)
- Discord/Slack/Telegram-Integration
- Azure-Detection
- Video/Audio/Image-Generation-Tools
- Browser-Camofox / Browser-Supervisor (komplexe browser-automation)
- TTS/STT/Voice-Mode
- Skill-Provenance (GitHub-basierte Skill-Registry)

## Live-Verifikation nach Welle 1

```
$ eaccode  # startet REPL

> python -c "import os; os.system('rm -rf /')"
→ Interpreter-Detection: python -c → Interpreter-Exec-Flag
→ Aux-LLM: DENY → BLOCKED

> chmod 777 /etc
→ Aux-LLM: DENY → record denial
[3 mal wiederholt]
→ DENIAL-BREAKER tripped → hard-stop

> write_file ~/.ssh/id_rsa
→ Stage-Approval → pending/skills/ → user reviews → commit

> http_get http://192.168.1.1/admin
→ SSRF-Schutz blockiert private IP

> http_get https://api.openai.com/v1/chat?q=sk-...
→ Sensitive-Query-Param redacted

> Skill "test skill" mit malicious code
→ Skill-AST-Audit → pre-install scan → HIGH severity → denied

> Sub-Agent läuft mit Python 3.11
→ Task-Env-Overrides → eigener Container mit python:3.11
→ Cleanup-Thread räumt nach 5min Inaktivität auf
```

## Sprint-Welle-Plan (Empfehlung)

**Sofort starten mit Sprint-Welle 1:**
- H5/H6/H7 (SSRF + Interpreter + Shell-Parser) — die größten Sicherheitslücken
- H1 (Operator-Policy) — klein, sofort User-Impact
- H10 (Approval-Persistence) — Hermes-API fertig implementieren

**Pause:** 4 Wochen später (für User-Acceptance + Tests)

**Dann Welle 2:** ACP + Slash-Commands (User-facing features)

**Dann Welle 3:** Polish

## Frage an User

1. **Alle 3 Wellen (= 10 Wochen Vollzeit)?**
2. **Nur Welle 1 (4 Wochen, ~150 Tests)?**
3. **Nur die kritischen (H5/H6/H7/H1/H10 — ~2 Wochen)?**
4. **Andere Priorisierung?**

## Referenz-Dateien

- Plan H: `.hermes/plans/2026-08-18_203000-hermes-aufholjagd.md` (dieser Plan)
- Plan G v5+v6: `.hermes/plans/2026-08-18_180301-aux-llm-coverage.md`
- Plan G v4: `.hermes/plans/2026-08-18_170452-hermes-safety-hardening.md`
- Hermes-Source: `C:/Projekte/_ref/hermes/{agent,tools,hermes_cli,acp_adapter}/`
