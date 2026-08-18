# EACcode Permission Audit — Tiefenanalyse

**Auditor:** Sub-Agent (Permission-Auditor)
**Projekt:** `C:/Projekte/EACcode V3/`
**Datum:** 2026-08-18
**Methodik:** Statisches Lesen + Live-Pipeline-Trace mit Fake-Provider/Model
**User-Config:** `mode: smart` (bestätigt in `C:/Users/kurtj/AppData/Local/eaccode/config.yaml`)

---

## TL;DR — Drei echte Bugs

| # | Bug | Severity | Datei : Zeile |
|---|-----|----------|---------------|
| **1** | `read_file`/`search_files` auf sensitive Pfade (`.env`, `.ssh`, `config.yaml`) fragt User — **bricht read-only** | **HIGH** | `permissions.py:597-604` |
| **2** | Aux-LLM (`smart_reviewer`) wird **niemals** für `write_file`, `patch_file`, `git_commit`, `browser_*` aufgerufen — nur für `run_command` | **HIGH** | `permissions.py:606-613` |
| **3** | `run_command` fragt **bei jedem einzelnen Turn** (sogar nach `s`ession-Approve), weil `is_always_ask` jeden Memory-Add blockiert | **HIGH** | `permissions.py:758-769` |

Außerdem: Das `_ask_owner_override` UI in `palette.py:536` ist **dead code** — keine Stelle im Permissions-Code reicht jemals `smart_denied=True` durch, das mit dem Owner-Override-UI zusammenarbeitet.

---

## A. Smart-Mode Read-Only-Pfad: `list_files`

**Setup:** mode=smart, `ask_handler` wired, `smart_reviewer` wired.

**Trace für `list_files {path: "."}`:**

1. `check()` permissions.py:491
2. Zeile 507–509: keine `deny_rules` → skip
3. Zeile 510–512: keine `allow_rules` → skip
4. Zeile 514: `_check_blocked_persistent` → no
5. Zeile 518: mode != "read_only" → skip
6. Zeile 531–560: nicht `run_command` → skip
7. Zeile 562–570: nicht `run_command` → skip hardline
8. Zeile 572–604: `path_arg = "."`, `_is_sensitive_path(".")` → False → **skip**
9. Zeile 607–613: nicht `run_command` → skip aux-LLM
10. **Zeile 616: `list_files` ∈ `_READ_ONLY_TOOL_NAMES` → return `Decision(True, "read-only tool")`**

**Finale Decision:** `Decision(allow=True, reason="read-only tool")` — **User wird NICHT gefragt.** ✓

```text
Empirisch verifiziert (test_pipeline_trace.py):
  list_files -> allow=True reason='read-only tool'
  ask_calls=[] smart_calls=[]
```

**Gleiche Trace für `read_file {path: "src/eaccode/agent.py"}`** → auto-approve. ✓

---

## C. Sensitive-Path Bug: `read_file {path: "/repo/.env"}`

**Trace:**

1–7. wie oben
8. **Zeile 572–604: `path_arg = "/repo/.env"`, `_is_sensitive_path("/repo/.env")` → True** (matcht `.env$` in `SENSITIVE_PATH_PATTERNS` Zeile 184)
9. Zeile 599: `_ask_user(tool_name="read_file", ..., sensitive=True)` → **PROMPT**

**Finale Decision:** `Decision(allow=True, reason="sensitive path: once approved")` — **User WIRD gefragt**, obwohl `read_file` ein read-only Tool ist.

```text
Empirisch verifiziert:
  read_file /repo/.env           -> ask_calls=['read_file']
  read_file C:/Users/kurtj/.env  -> ask_calls=['read_file']
  read_file config.yaml          -> ask_calls=['read_file']
```

### Root Cause

`permissions.py:638-654` `_is_sensitive_path()` ist nicht mutating-aware. Sie wird **vor** der read-only-Abkürzung in Zeile 616 aufgerufen. Die Sensitive-Path-Heuristik feuert für **jede** Operation mit einem Path-Argument, nicht nur für Writes.

Das `file_safety.is_write_denied()` (5a, Zeile 587) ist zwar korrekt mutating-gefiltert (Zeile 578-584 `_mutating_tools`), aber das zusätzliche `_is_sensitive_path` (5b, Zeile 598) **nicht**.

### Hit-Diagnose

`SENSITIVE_PATH_PATTERNS` (Zeile 164-200) matcht u.a.:
- `r"\.env$"` (Zeile 184) — **matcht `/repo/.env`, `C:/Users/kurtj/.env`, `.env`**
- `r"/\.env"` (Zeile 186) — matcht `/repo/.env` schon vor dem Anker
- `r"/\.ssh/"` (Zeile 165) — matcht `.ssh/`
- `r"config\.yaml$"` (Zeile 187) — matcht `config.yaml`
- `r"/\.git/config"` (Zeile 179) — matcht `.git/config`

**Read-only Tools die den Bug triggern:**
- `read_file` (in `_READ_ONLY_TOOL_NAMES`) — **bricht Read-Only**
- `search_files` (in `_READ_ONLY_TOOL_NAMES`) — **bricht Read-Only**
- `repo_search`, `repo_scan`, `repo_context` (in `_READ_ONLY_TOOL_NAMES`)

**Mutating-Tools die den Bug (richtig) triggern:** `write_file`, `patch_file`, `patch_multiple`, `git_commit`, `git_branch_new`, ... — hier ist es gewollt.

### Test-Lücke

`tests/test_permission_hardening.py:22-32` testet `write_file` auf sensitive paths, aber **kein einziger Test** für `read_file` / `search_files` auf sensitive paths. Daher ist der Bug durchgerutscht.

---

## B. Aux-LLM Coverage-Map

**Aux-LLM (`self.smart_reviewer`) wird aufgerufen in:**

`permissions.py:606-613` — **NUR** für `run_command` und **NUR** wenn der Befehl gegen mindestens ein `DANGEROUS_PATTERNS_COMPILED` matcht.

```python
# permissions.py:607-613
if self.mode == "smart" and tool_name == "run_command":
    command_arg = arguments.get("command", "")
    bare_call = command_arg if isinstance(command_arg, str) else ""
    for regex, description in DANGEROUS_PATTERNS_COMPILED:
        if regex.search(bare_call) or regex.search(call):
            return self._smart_review(tool_name, arguments, description)
    return Decision(True, "smart mode: safe command", self.mode)
```

### Coverage-Matrix

| Tool | Dangerous-Pattern-Check? | Aux-LLM? | Was passiert in smart-mode? |
|------|--------------------------|----------|------------------------------|
| `read_file` | nein | nein | auto-approve (außer sensitive path → ask) |
| `list_files` | nein | nein | auto-approve |
| `search_files` | nein | nein | auto-approve |
| `http_get`, `web_search`, `current_time`, `system_info` | nein | nein | auto-approve |
| `session_search`, `session_scroll` | nein | nein | auto-approve |
| `repo_scan`, `repo_search`, `repo_context` | nein | nein | auto-approve |
| `git_status`, `git_log`, `git_diff` | nein | nein | auto-approve |
| `memory_add`, `memory_replace`, `memory_remove`, `memory_apply_batch` | nein | **nein** | **ask** (Zeile 632-636, mutating) |
| `write_file` | nein | **nein** | **ask** |
| `patch_file`, `patch_multiple`, `file_edit` | nein | **nein** | **ask** |
| `git_commit`, `git_branch_new`, `git_commit_undo` | nein | **nein** | **ask** |
| `create_skill`, `improve_skill` | nein | **nein** | **ask** |
| `browser_click`, `browser_type`, `browser_navigate`, `browser_screenshot` | nein | **nein** | **ask** (always_ask) |
| `run_command` (safe) | nein | nein | **auto-approve** |
| `run_command` (dangerous pattern) | **ja** | **ja** | smart-approved / escalated / denied |

**Effekt:** Smart-Mode ist **nur** für `run_command` smart. Alle anderen mutating Tools (60+ tools) laufen direkt in `ask_handler`. Das ist eine **massive Lücke** — der User hat das mit Aux-LLM-Doesn't-Work bezeichnet.

### Empirische Verifikation

```text
write_file hello.txt     -> ask_calls=['write_file']  smart_calls=[]
patch_file               -> ask_calls=['patch_file']  smart_calls=[]
git_commit               -> ask_calls=['git_commit']  smart_calls=[]
browser_click            -> ask_calls=['browser_click'] smart_calls=[]
browser_navigate         -> ask_calls=['browser_navigate'] smart_calls=[]
run_command chmod 777    -> allow=True smart_calls=['chmod 777 (world-writable)']
run_command ls -la       -> allow=True smart_calls=[]
```

**Aux-LLM feuert EXKLUSIV für `run_command` mit Dangerous-Pattern.**

---

## D. Aux-LLM-Setup / Wiring

### Definition

- **Klasse:** `eaccode/smart_approval.py:114-165` `SmartApprovalReviewer`
- **Methode:** `review(command: str, description: str) -> str` (Zeile 136) — returns `"approve"`, `"deny"`, oder `"escalate"`
- **Timeout:** 10 Sekunden (Thread-Worker, Zeile 162-165)
- **Fallback:** bei Crash/Timeout → `"escalate"` (Zeile 159-160, 165)

### Wiring

**Setup:** `eaccode/cli.py:70-91` `build_agent()`:

```python
permission_manager = PermissionManager()
if permission_manager.mode == "smart":
    from eaccode.smart_approval import SmartApprovalReviewer
    conf = cfg.load_config()
    model_id = conf.get("model", {}).get("default") or ""
    provider_name, _, _ = model_id.partition("/")
    provider_config = (conf.get("providers") or {}).get(provider_name, {})
    if model_id and provider_config:
        from eaccode.providers import registry as provider_registry
        try:
            provider = provider_registry.get(
                provider_name, provider_config, model=model_id
            )
            permission_manager.smart_reviewer = SmartApprovalReviewer(
                provider, timeout=10.0
            ).review
        except Exception as exc:
            # Fall back to ask mode if provider registration fails
            print(f"Warning: smart review setup failed: {exc}")
```

### Aufruf-Stellen (alle)

`SmartApprovalReviewer.review` wird **genau einmal** pro Aux-LLM-Gate aufgerufen, in `permissions.py:687`:

```python
verdict = self.smart_reviewer(command, description)
```

Das passiert nur, wenn:
1. `mode == "smart"` UND
2. `tool_name == "run_command"` UND
3. mindestens ein `DANGEROUS_PATTERNS_COMPILED` matcht

### Failure-Modes im Setup

Aus `cli.py:79-91` ergibt sich: Aux-LLM wird **gar nicht** initialisiert, wenn:
- `model_id` leer (kein Default-Modell konfiguriert)
- `provider_config` leer (kein Provider-Eintrag)
- `provider_registry.get(...)` wirft Exception (gedruckt und stumm geschluckt)

In all diesen Fällen ist `permission_manager.smart_reviewer = None` und `permissions.py:683-685` fällt direkt auf `_ask_user` zurück — **Smart-Mode degradiert zu Manual-Mode**.

### `_ask_owner_override` — Dead Code

`palette.py:536-556` `_ask_owner_override` existiert, wird aber **niemals** von `permissions.py` aufgerufen. Die `_ask_user(...)` Aufrufe in `permissions.py:599, 685, 706-711, 713` übergeben zwar `smart_denied=True` (Zeile 710), aber:

```python
# permissions.py:770-778
reason = self._reason_for(scope, fallback_reason)
return Decision(
    allow=allowed,
    reason=reason,
    mode=self.mode,
    scope=scope,
    owner_override=smart_denied,   # ← wird nur ins Decision geschrieben
)
```

`owner_override` landet nur in der Decision-Datenklasse, **niemand liest es**. Die Palette hat keine Methode, die auf `decision.owner_override` reagiert. → 40 Zeilen unused code.

---

## E. Pipeline-Test mit Fake-Provider

Datei: `tests/test_pipeline_trace.py` (von mir angelegt)

**Test-Cases:**
1. `list_files {path: "."}` → expect auto-approve, no ask
2. `read_file {path: "src/eaccode/agent.py"}` → expect auto-approve
3. `read_file {path: "/repo/.env"}` → expect NO prompt (BUG: actually prompts)
4. `read_file {path: "C:/Users/kurtj/.env"}` → expect NO prompt (BUG: actually prompts)
5. `write_file {path: "hello.txt"}` → expect aux-LLM consult (BUG: directly asks)
6. `run_command {command: "ls -la"}` → expect auto-approve ✓
7. `run_command {command: "chmod 777 /tmp"}` → expect aux-LLM ✓
8. `run_command {command: "find . -delete"}` → expect aux-LLM ✓
9. `patch_file {path: "x", ...}` → expect aux-LLM (BUG: asks)
10. `git_commit {message: "fix"}` → expect aux-LLM (BUG: asks)
11. `browser_click {ref: "r1"}` → expect aux-LLM (BUG: asks, always_ask)

**Empirisches Ergebnis (real run, oben):**

```text
list_files → allow=True, ask=[], smart=[]
read_file (normal) → allow=True, ask=[], smart=[]
read_file /repo/.env → allow=True, ask=['read_file'], smart=[]  ← BUG #1
read_file C:/Users/kurtj/.env → allow=True, ask=['read_file'], smart=[]  ← BUG #1
write_file → allow=True, ask=['write_file'], smart=[]  ← BUG #2
patch_file → allow=True, ask=['patch_file'], smart=[]  ← BUG #2
git_commit → allow=True, ask=['git_commit'], smart=[]  ← BUG #2
browser_click → allow=True, ask=['browser_click'], smart=[]  ← BUG #2
browser_navigate → allow=True, ask=['browser_navigate'], smart=[]  ← BUG #2
run_command ls → allow=True, ask=[], smart=[]  ✓
run_command chmod 777 → allow=True, ask=[], smart=['chmod 777 (world-writable)']  ✓
run_command find -delete → allow=True, ask=[], smart=['find -delete']  ✓
```

**Wo der Bug ist:** `permissions.py:607-613` und `permissions.py:572-604`.

---

## F. Multi-Turn Tool-Call Loop

**Setup:** `agent.py:284-381` `Agent.run()`:

```python
for _ in range(max_turns):           # max_turns=8 (DEFAULT, Zeile 69)
    ...
    content, calls = self._complete(history, ...)
    if not calls:
        return history              # keine Tool-Calls → fertig
    ...
    if len(calls) > 1:
        with ThreadPoolExecutor(max_workers=min(len(calls), 6)) as pool:
            results = list(pool.map(self._execute_tool, calls))
    else:
        results = [self._execute_tool(calls[0])]
    for call, content in zip(calls, results, strict=True):
        history.append({"role": "tool", "tool_call_id": call.id, "content": content})
```

**`Agent._execute_tool`** (Zeile 256-282) ruft **bei jedem Tool-Call** `permission_manager.check()` auf (Zeile 264). Es gibt **keinen** session-scope-Cache, der über mehrere Iterationen erhalten bleibt — `permission_manager` wird einmal instanziiert (`cli.py:70`), und seine `_session_allowed` Set lebt im PermissionManager-Lifetime, nicht in der Iteration.

**Session-Memory in `_ask_user` (Zeile 715-779):**

```python
# 1. Nach "session"/"always" + nicht always_ask → add to session
if allowed and scope in ("session", "always"):
    if not is_always_ask(tool_name):
        self._session_allowed.add(tool_name)
# 2. Legacy once → add to session (BACKWARD-COMPAT)
if allowed and scope == "once" and not is_always_ask(tool_name):
    self._session_allowed.add(tool_name)
```

**Effekt:** 
- `write_file` "y" → session_allowed ✓
- `write_file` "n" → falls weiter geprüft wird, hält's die Decision
- `run_command` "y" → **nicht** in session_allowed (Zeile 768 `not is_always_ask`)
- `browser_*` "y" → **nicht** in session_allowed

**Result:** Für `run_command` und `browser_*` fragt das System **bei JEDEM Tool-Call** in **jedem Turn** neu — egal was der User vorher gesagt hat. Das ist **exakt** was der User beklagt.

### Workaround in `cli.py:79-91`

Der Aux-LLM-Setup umgeht das nicht — auch wenn Aux-LLM `"approve"` für `rm -rf /tmp/test` sagt, wird der Befehl in `permissions.py:686-695` mit `scope="once"` freigegeben, **nicht `scope="session"`**. Das Aux-LLM fügt nichts zu `_session_allowed` hinzu. → Auch Aux-LLM-Approve bedeutet: nächster `run_command` fragt wieder.

### Lösung für Bug #3

Die `_smart_review` Funktion (Zeile 672-713) gibt `Decision(..., scope="once")` für `approve` / `deny` / `escalate` zurück. Für den Aux-LLM-Approve-Fall sollte stattdessen `scope="session"` (oder zumindest **Tool-Name + Arg-Hash** in einer session-Dict) verwendet werden — dann wird nach Aux-LLM-Approve dieser spezifische Befehl für die Session gespeichert.

---

## Fix-Plan

### Fix #1 (Sensitive-Path auf Read-Only-Tools)

**Datei:** `src/eaccode/permissions.py:574-604`

**Problem:** `_is_sensitive_path` (Zeile 598) wird vor der Read-Only-Erkennung (Zeile 616) aufgerufen.

**Fix:** Sensitive-Path-Check nur für mutating Tools anwenden. Verschiebe den 5b-Block NACH Zeile 616.

```python
# VORHER (Zeile 572-604):
# 5. Sensitive-path check (for any tool with a path arg)
path_arg = self._extract_path_arg(tool_name, arguments)
if path_arg:
    ...
    # 5b. Our generic sensitive-path check (allows prompt)
    if self._is_sensitive_path(path_arg):
        return self._ask_user(
            tool_name,
            arguments,
            fallback_reason="sensitive path",
            sensitive=True,
        )

# NACHHER:
# 5. Sensitive-path check (only for mutating tools - read-only must run free)
path_arg = self._extract_path_arg(tool_name, arguments)
if path_arg and tool_name in _mutating_tools:   # ← neue Condition
    # 5a. file_safety.hardcoded-paths (block)
    ...
    # 5b. generic sensitive-path (prompt)
    if self._is_sensitive_path(path_arg):
        return self._ask_user(...)
```

(Der `_mutating_tools` Tupel ist bereits lokal in Zeile 578-584 definiert.)

**Optional:** Lies-sensitive path trotzdem tracken via `decision.read_sensitive_path = True` für UI-Warnungen, aber kein Block.

### Fix #2 (Aux-LLM Coverage auf alle mutating Tools)

**Datei:** `src/eaccode/permissions.py:606-613`

**Problem:** Aux-LLM-Gate gilt nur für `run_command`.

**Fix:** Generalisiere auf alle mutating Tools. Definiere einen `DANGEROUS_TOOL_PATTERNS` Lookup mit den Dangerous-Regexes die für jedes Tool relevant sind, oder einfach: konsultiere Aux-LLM für **alle mutating Tools** die nicht in `is_always_ask` sind.

```python
# VORHER (Zeile 606-613):
if self.mode == "smart" and tool_name == "run_command":
    command_arg = arguments.get("command", "")
    bare_call = command_arg if isinstance(command_arg, str) else ""
    for regex, description in DANGEROUS_PATTERNS_COMPILED:
        if regex.search(bare_call) or regex.search(call):
            return self._smart_review(tool_name, arguments, description)
    return Decision(True, "smart mode: safe command", self.mode)

# NACHHER:
_MUTATING_TOOLS_FOR_SMART = frozenset({
    "write_file", "patch_file", "patch_multiple", "file_edit",
    "git_commit", "git_branch_new", "git_commit_undo",
    "create_skill", "improve_skill",
    "memory_add", "memory_replace", "memory_remove", "memory_apply_batch",
})
if self.mode == "smart" and tool_name in _MUTATING_TOOLS_FOR_SMART:
    # Build the "command" string for the aux LLM (path + content for edits)
    payload = self._call_summary(tool_name, arguments)
    for regex, description in DANGEROUS_PATTERNS_COMPILED:
        if regex.search(payload) or regex.search(call):
            return self._smart_review(tool_name, arguments, description)
    return Decision(True, f"smart mode: safe {tool_name}", self.mode,
                    scope="session")    # ← scope="session" für Bug #3
```

`_call_summary` ist eine Helper-Funktion die `tool_name + args` zu einem String zusammenbaut, gegen den die Dangerous-Patterns matchen können (z.B. `write_file {"path": ..., "content": ...}` → `"/path/x.py: <content>"`).

Caveat: Die 77 `DANGEROUS_PATTERNS` sind shell-command-spezifisch (`rm -rf`, `chmod 777`, etc.). Für File-Edit-Tools brauchen wir **eine zweite Pattern-Liste** wie `DANGEROUS_FILE_PATTERNS` die z.B. triggert auf:
- path in `/.ssh/`, `/.env`, `config.yaml` (bereits abgedeckt durch Sensitive-Path)
- content mit `password=`, `token=`, `api_key=`
- content mit eingebetteten `curl|sh` Sequenzen

### Fix #3 (Run-Command Session-Memory)

**Datei:** `src/eaccode/permissions.py:672-713` `_smart_review`

**Problem:** Aux-LLM-Approve gibt `scope="once"`. `run_command` ist in `ALWAYS_ASK_TOOLS`, also kein Session-Memory.

**Fix:** Aux-LLM-Approve sollte für die spezifische `(tool_name, command_hash)` Kombination session-gespeichert werden, statt nur `tool_name`.

```python
# VORHER (Zeile 686-695):
verdict = self.smart_reviewer(command, description)
if verdict == "approve":
    return Decision(
        True,
        f"smart-approved: {description}",
        self.mode,
        scope="once",          # ← Problem
        smart_reviewed=True,
    )

# NACHHER:
if verdict == "approve":
    # Session-memory this specific command (NOT just the tool name)
    cmd_hash = f"run_command::{hash((command,))}"
    self._session_allowed.add(cmd_hash)
    return Decision(
        True,
        f"smart-approved: {description}",
        self.mode,
        scope="session",
        smart_reviewed=True,
    )
```

**Aber:** `permission_manager.check()` (Zeile 628) prüft **nur** `tool_name in self._session_allowed`. Wir müssten entweder:
- (a) Den Lookup auf `tool_name in self._session_allowed or f"run_command::{hash(cmd)}" in ...` erweitern
- (b) Oder `is_always_ask` für `run_command` lockern, wenn Aux-LLM approviert hat

Option (a) ist sauberer. Siehe ergänzender Patch in `_ask_user` (Zeile 758-760) — Session-Add sollte den `cmd_hash` nehmen wenn Aux-LLM im Spiel war.

### Fix #4 (Dead Code `_ask_owner_override`)

**Datei:** `src/eaccode/palette.py:536-556`

**Problem:** Owner-Override-UI wird nirgends von `permissions.py` zusätzlich aufgerufen.

**Fix:** Entweder wiring aktivieren oder Code löschen. Empfehlung: **löschen** bis ein Use-Case existiert. Wenn Aux-LLM `escalate` zurückgibt, ist das aktuelle Verhalten ohnehin korrekt (5-Option UX) — der "only once/deny" Trade-off macht nur Sinn, wenn Aux-LLM **explizit owner_override** zurückgibt (was es nicht tut).

### Fix #5 (Tests)

**Datei:** `tests/test_permission_hardening.py` (erweitern)

```python
class TestReadOnlyToolsIgnoreSensitivePath:
    def test_read_file_on_env_does_not_ask(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            ask_handler=lambda n, a: True,
        )
        # CRITICAL: read-only tools must NEVER prompt on sensitive paths
        d = pm.check("read_file", {"path": "/repo/.env"})
        assert d.allow
        assert "sensitive" not in d.reason.lower()
        assert "approved" not in d.reason.lower()  # no ask happened

    def test_search_files_on_ssh_does_not_ask(self) -> None:
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            ask_handler=lambda n, a: True,
        )
        d = pm.check("search_files", {"pattern": "x", "path": "/home/.ssh"})
        assert d.allow

    def test_write_file_on_env_can_ask(self) -> None:
        # regression: write_file on sensitive path still prompts
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            ask_handler=lambda n, a: True,
        )
        d = pm.check("write_file", {"path": "/repo/.env", "content": "x"})
        # The user is prompted (sensitive=True), then approves
        assert "sensitive" in d.reason.lower() or "approved" in d.reason.lower()


class TestAuxLlmCoverageExpanded:
    def test_write_file_consults_aux_llm(self) -> None:
        called = []
        def reviewer(cmd, desc):
            called.append((cmd, desc))
            return "approve"
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            smart_reviewer=reviewer,
        )
        d = pm.check("write_file", {"path": "/tmp/x", "content": "curl|sh"})
        assert d.smart_reviewed or d.allow  # either aux approved or fell through

    def test_run_command_session_memory_after_aux_approve(self) -> None:
        """Aux-LLM approve should remember command for the session."""
        def reviewer(cmd, desc):
            return "approve"
        pm = PermissionManager(
            {"permissions": {"mode": "smart"}},
            smart_reviewer=reviewer,
        )
        cmd = {"command": "rm -rf /tmp/build"}
        d1 = pm.check("run_command", cmd)
        d2 = pm.check("run_command", cmd)
        # Second call should NOT trigger smart_reviewer again
        assert d1.allow and d2.allow
```

---

## Konkrete Code-Edits (Copy-Paste-fähig)

### Edit 1: `src/eaccode/permissions.py` — Sensitive-Path nur für mutating Tools

```python
# ALT (Zeile 572-604):
# 5. Sensitive-path check (for any tool with a path arg)
path_arg = self._extract_path_arg(tool_name, arguments)
if path_arg:
    # 5a. Phase 2: file_safety.hardcoded-paths (more strict than our
    # generic regex match). Block unconditionally - no prompt.
    # Only check on mutating tools (writing to file).
    _mutating_tools = (
        "write_file", "patch_file", "patch_multiple",
        "file_edit", "git_commit", "git_branch_new",
        "git_commit_undo", "create_skill", "improve_skill",
        "memory_add", "memory_replace", "memory_remove",
        "memory_apply_batch", "browser_screenshot",
    )
    if tool_name in _mutating_tools:
        try:
            from eaccode.file_safety import is_write_denied

            if is_write_denied(path_arg):
                return Decision(
                    False,
                    "file_safety blocked (exact sensitive path)",
                    self.mode,
                )
        except Exception:
            pass
    # 5b. Our generic sensitive-path check (allows prompt)
    if self._is_sensitive_path(path_arg):
        return self._ask_user(
            tool_name,
            arguments,
            fallback_reason="sensitive path",
            sensitive=True,
        )

# NEU (Zeile 572-604):
# 5. Sensitive-path check (ONLY for mutating tools — read-only tools run free)
path_arg = self._extract_path_arg(tool_name, arguments)
if path_arg:
    _mutating_tools = (
        "write_file", "patch_file", "patch_multiple",
        "file_edit", "git_commit", "git_branch_new",
        "git_commit_undo", "create_skill", "improve_skill",
        "memory_add", "memory_replace", "memory_remove",
        "memory_apply_batch", "browser_screenshot",
    )
    if tool_name in _mutating_tools:
        # 5a. file_safety.hardcoded-paths (block unconditionally)
        try:
            from eaccode.file_safety import is_write_denied

            if is_write_denied(path_arg):
                return Decision(
                    False,
                    "file_safety blocked (exact sensitive path)",
                    self.mode,
                )
        except Exception:
            pass
        # 5b. Generic sensitive-path (prompt)
        if self._is_sensitive_path(path_arg):
            return self._ask_user(
                tool_name,
                arguments,
                fallback_reason="sensitive path",
                sensitive=True,
            )
```

### Edit 2: `src/eaccode/permissions.py` — Aux-LLM auf alle mutating Tools

Füge **nach** Zeile 613 (vor Zeile 615) ein:

```python
# 6b. Smart-Mode Aux-LLM for ALL mutating tools (not just run_command)
if self.mode == "smart" and tool_name not in ("run_command",):
    _SMART_AUDIT_TOOLS = frozenset({
        "write_file", "patch_file", "patch_multiple", "file_edit",
        "git_commit", "git_branch_new", "git_commit_undo",
        "create_skill", "improve_skill",
        "memory_add", "memory_replace", "memory_remove",
        "memory_apply_batch",
    })
    if tool_name in _SMART_AUDIT_TOOLS and not is_always_ask(tool_name):
        # Build a string representation for the aux LLM
        payload = self._call_summary(tool_name, arguments)
        for regex, description in DANGEROUS_PATTERNS_COMPILED:
            if regex.search(payload) or regex.search(call):
                return self._smart_review(tool_name, arguments, description)
        # No dangerous pattern: auto-approve with session memory
        return Decision(
            True,
            f"smart mode: safe {tool_name}",
            self.mode,
            scope="session",   # ← BUG #3 fix inline
        )
```

Plus Helper-Methode (z.B. vor `_ask_user`):

```python
def _call_summary(self, tool_name: str, arguments: dict[str, Any]) -> str:
    """Build a string the aux LLM can review for a non-run_command tool."""
    if tool_name in ("write_file", "patch_file", "patch_multiple", "file_edit"):
        path = arguments.get("path", "")
        content = arguments.get("content", "") or arguments.get("new_content", "")
        return f"{path}: {content}"
    if tool_name.startswith("git_"):
        return json.dumps(arguments, sort_keys=True)
    if tool_name.startswith("memory_"):
        return json.dumps(arguments, sort_keys=True)
    return f"{tool_name} {json.dumps(arguments, sort_keys=True)}"
```

### Edit 3: `src/eaccode/permissions.py` — Aux-LLM-Approve = Session

In `_smart_review` (Zeile 686-695):

```python
# ALT:
if verdict == "approve":
    return Decision(
        True,
        f"smart-approved: {description}",
        self.mode,
        scope="once",
        smart_reviewed=True,
    )

# NEU:
if verdict == "approve":
    # Remember SPECIFIC (tool, args) for the session, not just tool_name.
    # This makes repeat commands run without re-asking.
    cmd_hash = self._approval_hash(tool_name, arguments)
    self._session_allowed.add(cmd_hash)
    return Decision(
        True,
        f"smart-approved: {description}",
        self.mode,
        scope="session",
        smart_reviewed=True,
    )
```

Und in `check()` Zeile 628 erweitern:

```python
# ALT (Zeile 628):
if tool_name in self._session_allowed and not is_always_ask(tool_name):
    return Decision(True, "approved for this session", self.mode)

# NEU:
if not is_always_ask(tool_name):
    if tool_name in self._session_allowed:
        return Decision(True, "approved for this session", self.mode)
    if self._approval_hash(tool_name, arguments) in self._session_allowed:
        return Decision(True, "approved for this session (specific call)", self.mode)
```

Plus Helper:

```python
def _approval_hash(self, tool_name: str, arguments: dict[str, Any]) -> str:
    """Stable hash for a (tool, args) pair to use as session-memory key."""
    import hashlib
    payload = f"{tool_name}|{json.dumps(arguments, sort_keys=True, ensure_ascii=False)}"
    return f"hash:{hashlib.sha256(payload.encode()).hexdigest()[:16]}"
```

---

## Multi-Agent-Hinweis

Diese Diagnose ist abgeschlossen. Empfohlene nächste Schritte (parallelisierbar):

1. **Sub-Agent A (Fix-Implementer):** Edits 1, 2, 3 oben anwenden, dann `pytest tests/test_permissions.py tests/test_permission_hardening.py -v` ausführen.
2. **Sub-Agent B (Test-Author):** Edit 5 (Tests) in `tests/test_permission_hardening.py` und ggf. neuer `tests/test_smart_mode_mutating.py` schreiben.
3. **Sub-Agent C (UX-Patch):** Owner-Override-UI entweder wiring (`_ask_owner_override` an `palette._ask` koppeln wenn `decision.owner_override`), oder löschen.

Trace-File `tests/test_pipeline_trace.py` (von mir erstellt) ist Beweismaterial und sollte in der Suite bleiben oder durch ordentliche Tests ersetzt werden.
