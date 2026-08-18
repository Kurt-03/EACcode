# Plan B: Permission-System Hardening

> **Status:** DRAFT — wartet auf User-Freigabe
> **Auslöser:** Audit 2 fand **kritische Security-Bugs** im Permission-System
> **Priorität:** **KRITISCH** (kann sensitive Daten manipulieren ohne User-Wissen)

## Diagnose (Audit 2)

| Befund | Severity | Detail |
|---|---|---|
| **Aux-LLM nur für `run_command`** | KRITISCH | Smart-Mode ist "smart" nur für Bash. Andere mutating Tools (`write_file`, `git_commit`, `browser_*`, `memory_*`, alle MCP-Mutating) gehen direkt zum User oder Auto-Approve, **ohne Aux-Analysis** |
| **Sensitive-Paths nicht geprüft** | KRITISCH | Mode-Hint sagt `.ssh/`, `.env`, `config.yaml` werden gefragt — aber `check()` tut's nicht. `write_file .ssh/id_rsa` in smart mode → **auto-approve** (via session_memory). Echter Datenklau. |
| **`is_always_ask()` toter Code** | KRITISCH | `check()` ruft `is_always_ask()` nie. Browser-Tools werden in manual mode **an Session erinnert** — falsch |
| **Deny-by-default ohne ask_handler** | HOCH | Wenn `_wire_agent_gate` nicht läuft (Cron, Subprocess, headless): alle mutating Tools außer `run_command` werden **geblockt** |
| **READ_ONLY_TOOLS hardcoded** | HOCH | Drift zwischen `make_*_tools()` und Permissions-Whitelist. Neue Tools müssen 3 Stellen updaten |
| **Hardline nur für `run_command`** | HOCH | `write_file config.yaml` würde Hardline-Match versuchen, aber Hardline ist nur im `run_command`-Branch |
| **Mode-Hint lügt** | MITTEL | "Sensitive paths prompt" — implementation fehlt |

## Fixes

### 1. `Tool`-Dataclass mit `mutates=True/False` Tag

```python
@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    mutates: bool = False      # NEU
    returns: str = ""           # NEU (von Plan A)
```

### 2. READ_ONLY_TOOLS automatisch ableiten

`READ_ONLY_TOOLS`-frozenset entfernen. Stattdessen:

```python
def is_read_only_tool(tool: Tool) -> bool:
    return not tool.mutates
```

`make_*_tools()` factories nutzen das. **Eine** Quelle der Wahrheit.

### 3. always_ask-Tag in Tool-Dataclass

```python
@dataclass
class Tool:
    ...
    mutates: bool = False
    always_ask: bool = False   # NEU
```

`run_command`, `browser_*`, mutating MCP-Tools = `always_ask=True`.

### 4. check() Pipeline Rewrite (NEUES LAYOUT)

```python
def check(self, tool_name, arguments):
    call = self.call_text(tool_name, arguments)
    
    # 1. deny rule (wins)
    for rule in self.deny_rules:
        if re.search(rule, call, re.IGNORECASE):
            return DECISION_DENY(f"denied by rule: {rule}")
    
    # 2. allow rule
    for rule in self.allow_rules:
        if re.search(rule, call, re.IGNORECASE):
            return DECISION_ALLOW(f"allowed by rule: {rule}")
    
    # 3. read_only mode
    if self.mode == "read_only":
        return ALLOW if is_read_only_tool(tool) else DENY
    
    # 4. Hardline (für run_command - commands)
    if tool_name == "run_command":
        if HARDLINE.match(arguments.get("command", "")):
            return DENY("hardline")
    
    # 5. Sensitive-Path (für tools mit "path" parameter)
    path = arguments.get("path") or arguments.get("file_path")
    if path and SENSITIVE_PATH.match(path):
        return self._ask_or_smart(tool_name, arguments, reason="sensitive path")
    
    # 6. Smart-Mode Aux-LLM-Review (für mutating tools)
    if self.mode == "smart" and tool_is_mutating(tool):
        return self._smart_review(tool_name, arguments)
    
    # 7. Read-only tools
    if is_read_only_tool(tool):
        return ALLOW("read-only")
    
    # 8. always_ask tools (manual mode): jedes Mal fragen, kein session memory
    # 9. off mode: auto-approve
    # 10. session-approved tools
    # 11. ask_handler (manual mode default)
```

### 5. SENSITIVE_PATHS-Check ist Argument-bewusst

Extraktion funktioniert für ALLE Tools die `path` / `file_path` / `target_path` haben:

```python
def _extract_path(tool_name, arguments):
    for key in ["path", "file_path", "target_path"]:
        if key in arguments:
            return arguments[key]
    return None
```

Plus `git_*` tools: Pfad via `repo://cwd`-construction.

### 6. Aux-LLM-Review erweitert auf alle mutating Tools

```python
def _smart_review(self, tool_name, arguments):
    # Same as today, but uses tool-aware prompt
    prompt = _build_smart_prompt(tool_name, arguments)
    verdict = self.smart_reviewer(prompt, "...")
    # 'approve' | 'deny' | 'escalate'
```

`smart_reviewer` signature bleibt `(str, str) -> str`.

### 7. is_always_ask enforcement

In `check()`:

```python
if ask_handler is not None:
    allowed = ask_handler(tool_name, arguments)
    if allowed and not is_always_ask(tool_name):
        # only remember non-always-ask tools
        self._session_allowed.add(tool_name)
    else:
        # always-ask tools prompt every time
        pass
```

Plus: bei `is_always_ask(tool_name)` return KEIN session-allow.

### 8. Mode-Hint korrigieren

Update `mode_hint(SMART)` so dass es **nur** implementiertes Verhalten beschreibt:

```python
f"""
## Permission mode: SMART

Safe commands auto-approve. Mutating tool calls that target sensitive
paths (.ssh/, .env, config.yaml, /etc/) prompt for approval. Other
mutating tools go through an aux LLM review.

Tip: /approvals to see or change mode.
"""
```

## Schritte

1. `src/eaccode/agent.py`: `Tool`-Dataclass erweitern (`mutates`, `always_ask`, `returns`)
2. Alle `make_*_tools()`-Factories updaten mit den neuen Tags
3. `src/eaccode/permissions.py`: `READ_ONLY_TOOLS` entfernen, `is_read_only_tool(tool)` Helper
4. `permissions.py`: `check()` Rewrite mit der neuen Pipeline
5. `permissions.py`: `SENSITIVE_PATHS` Check in `check()` (für alle Tools mit path-Arg)
6. `permissions.py`: `is_always_ask` enforcement in session-memory logic
7. `permissions.py`: `mode_hint()` updaten (Implementierungs-getreue Beschreibung)
8. CLI `build_agent()`: wired correctly mit Permissions + Tags
9. Tests: 30+ neue Tests in `tests/test_permissions.py` + `tests/test_tool_schemas.py`
10. Brain: `permissions.md` updaten mit neuer Pipeline

## Inventur

- 5-7 Dateien geändert
- ~600-1000 Zeilen Code-Änderung
- ~30 Tests neu/erweitert
- ~8-10 Commits

## Was **nicht** im Scope

- Multi-Aux-LLM (Phase 2)
- Reasoning-Effort (eigener Plan)
- Pattern-Auto-Tuning basierend auf User-Verhalten
- Cross-Session Permission-Memory (nur in `_session_allowed`)
- Multi-User Permission-Isolation
