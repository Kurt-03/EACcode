# Plan A: Tool-Property-Descriptions + Result-Format Documentation

> **Status:** DRAFT — wartet auf User-Freigabe
> **Auslöser:** Audit 1 fand 26/38 (68%) Property-Descriptions fehlen, Result-Format undokumentiert
> **Priorität:** Hoch (UX, aber nicht security)

## Ziel

Jedes Tool liefert dem Model:

1. **Property-Description** pro Parameter (`input_schema.properties.{name}.description`)
2. **`required`-Liste** korrekt
3. **`returns`-Description** in der Tool-Desc selbst ("Returns the file content as a plain string, truncated to 8000 chars. Returns 'Error: ...' if not readable.")

## Was aktuell fehlt

| Tool | Property-Desc? | required? | returns in Tool-Desc? |
|---|---|---|---|
| `read_file` | ❌ nein | ✅ ja | ❌ nein |
| `write_file` | ❌ nein | ✅ ja | ❌ nein |
| `list_files` | ❌ nein | – | ❌ nein |
| `search_files` | ❌ nein | ✅ ja | ❌ nein |
| `run_command` | ❌ nein | ✅ ja | ❌ nein |
| `http_get` | ❌ nein | ✅ ja | ❌ nein |
| `web_search` | ❌ nein | ✅ ja | ❌ nein |
| `current_time` | n/a | n/a | ❌ nein |
| `system_info` | n/a | n/a | ❌ nein |
| `file_edit` | ✅ ja | – | ❌ nein |
| `patch_file` | ✅ ja | – | ❌ nein |
| `patch_multiple` | ✅ ja | – | ❌ nein |
| `undo_edit` | ❌ nein | – | ❌ nein |
| `git_*` (6) | ❌ nein | ❌ nein | ❌ nein |
| `memory_*` (4) | ❌ nein | ❌ nein | ❌ nein |
| `repo_*` (3) | ✅ teilweise | – | ❌ nein |
| `session_*` (2) | ❌ nein | ❌ nein | ❌ nein |
| `run_tests` | ✅ teilweise | – | ❌ nein |
| `browser_*` (6) | ❌ nein | ❌ nein | ❌ nein |
| `skill_*` (3) | ✅ teilweise | – | ❌ nein |

**Tot:** ~30 Tools brauchen Upgrade.

## Implementierung

### Schnittstelle

Erweitere `Tool` Dataclass (in `agent.py`):

```python
@dataclass
class Tool:
    name: str
    description: str           # erweitert: "Returns ... when successful, 'Error: ...' when not"
    func: Callable[..., Any]
    parameters: dict[str, Any] = field(default_factory=dict)
    # New:
    mutates: bool = False      # Permission-Tag (von Plan B gelesen)
    returns: str = ""           # Optional separate returns-Description
```

### Properties befüllen

Jedes Schema-Dict erweitern mit `"description": "..."`. Beispiel `read_file`:

```python
"properties": {
    "path": {
        "type": "string",
        "description": "Absolute or relative file path. Parent dirs auto-created on write.",
    },
    "max_chars": {
        "type": "integer",
        "description": "Truncate file content after this many chars (default: 8000).",
    },
}
```

### Returns-Description im Tool-Desc

Suffix-Pattern: `Returns: <text>. Error: <text>.`

Beispiele:

| Tool | Returns-Suffix |
|---|---|
| `read_file` | " Returns: file content as plain string. Error: 'Error: file not readable: <path>' when path is binary/missing." |
| `run_command` | " Returns: stdout+stderr combined, plus newline+'(exit N)' on non-zero. Error: 'Error: command timed out after Ns'." |
| `write_file` | " Returns: 'wrote <bytes> bytes to <path>' on success. Error: 'Error: ...' on permission-denied or parent-dir-creation failed." |
| `search_files` | " Returns: 'path:line: <matched line>' lines, or '(no matches)'. Error: 'Error: ...' on ripgrep failure." |
| `git_commit` | " Returns: hash on success. Error: 'Error: ...' on git failure. Policy: NEVER commit unless tests pass." |

### Standardisierte Error-Format

Alle Tools returnen einen **String**, der mit `"Error: "` prefix beginnt wenn was schief ging. Im Tool-Desc dokumentiert.

## Was ist **nicht** im Scope

- Kein Multi-Language-Output
- Kein automatisches Inference ("guess" properties from function signature via `inspect.signature()`)
- Kein Schema-Auto-Validation
- Kein `examples` field

## Test-Strategie

Neue Tests in `tests/test_tool_schemas.py`:

```python
def test_all_built_in_tools_have_property_descriptions():
    for tool in BUILTIN_TOOLS:
        for prop_name in tool.parameters.get("properties", {}):
            assert "description" in tool.parameters["properties"][prop_name], ...

def test_each_tool_documents_returns_format():
    for tool in [...all tools...]:
        assert "returns" in tool.description.lower() or "error" in tool.description.lower(), ...
```

## Inventur

- ~30 Tool-Defs, je 5-10 Zeilen Update
- ~200 Lines Code-Änderung
- ~50 Lines Tests
- Total: ~12 Commits (einer pro Tool-Modul + Tool-Schema-Update + Tests)
