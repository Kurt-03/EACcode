# Replace LiteLLM with models.dev + Anthropic SDK — Plan

> **Status:** `DRAFT` — wartet auf User-Freigabe. Nicht ausführen.
> **User-Auftrag:** "litellm raus, models.dev rein, das für alle (auch zukünftigen) Provider umstellen."
> **Referenz:** `C:/Projekte/_ref/hermes/agent/{models_dev.py,anthropic_adapter.py}` (alles schon implementiert).

**Goal:** LiteLLM komplett aus eaccode entfernen. Statt dessen direkt die `anthropic` SDK (für Anthropic-Messages-API) und `openai` SDK (für OpenAI-Compatible-Provider) verwenden. Model-Catalog aus `models.dev` (`https://models.dev/api.json`) beziehen — wie Hermes.

**Architecture:** Drei Schichten:
1. **`models_dev.py` (NEU)** — Mirror von Hermes' `models_dev.py`, aber für eaccode zugeschnitten (~300-400 Zeilen statt 903). Liefert Provider- + Model-Metadaten.
2. **`providers.py` (NEU, ersetzt `router.py`)** — Ein Adapter pro Provider-Family: Anthropic (`anthropic` SDK) + OpenAI-Compatible (`openai` SDK). Beide nutzen models.dev für Metadaten.
3. **`agent.py` (REFACTOR)** — Stream-Callback wird zur generischen `StreamChunk` (kind="text" | "reasoning" | "tool_call"). Provider-Adapter normalisieren.

**Tech Stack:**
- ❌ Entfernen: `litellm>=1.60`
- ✅ Hinzufügen: `anthropic>=0.39` (für Anthropic-Messages-API), `openai>=1.60` (für OpenAI-compat), `requests>=2.33` (für models.dev)
- ✅ ESLint-style: `httpx` ist in `anthropic` schon drin
- ✅ Alle anderen Pakete bleiben

---

## 1. Was ist kaputt (Diagnose)

### 1.1 LiteLLM macht 4 Sachen falsch
1. **OpenAI-Format-Routing** statt Anthropic-Messages-Format für MiniMax → MiniMax hat eigene Tool-Call-Format, LiteLLM merkt das nicht
2. **`x-api-key`-Header** statt korrektem `Authorization: Bearer ...` für MiniMax (siehe Hermes `_requires_bearer_auth`)
3. **Falsche Beta-Header** — Hermes strippt `fine-grained-tool-streaming-2025-05-14` für MiniMax, weil MiniMax die ablehnt
4. **Kein Anthropic-Streaming-Format** — MiniMax-M3 streamt eigentlich als Anthropic Messages Stream, LiteLLM normalisiert das zu OpenAI, verliert dabei reasoning_content → Antworten werden abgeschnitten

### 1.2 Hermes macht alles direkt
- `anthropic.Anthropic` SDK → Messages API für MiniMax, Anthropic, OpenAI via Bedrock, etc.
- `openai.OpenAI` SDK → OpenAI-Compatible-Format für OpenAI, OpenRouter, Groq, Together, etc.
- `models.dev/api.json` → Catalog mit 4000+ Models, 109+ Provider, Metadata (context, pricing, capabilities)
- Per-Provider-Anpassungen in `auxiliary_client.py` (für OpenAI-Family) und `anthropic_adapter.py` (für Anthropic-Family)

### 1.3 Inventory — was muss raus
- **Source:** 3 `import litellm` + 1 `litellm.completion`-Aufruf in `src/eaccode/router.py` (Z. 139-142, 162-165)
- **Dep:** `litellm>=1.60` in `pyproject.toml` Z. 11
- **Tests:** 11 `import litellm` + 10 `monkeypatch.setattr(litellm, "completion", ...)` in `tests/test_agent.py`, `tests/test_palette.py`, `tests/test_commands.py`
- **Docs:** 0 (kein litellm in `docs/` oder `brain/`)
- **Infrastruktur:** `litellm.suppress_debug_info = True` (cosmetic, fällt weg)

---

## 2. Soll-Bild (Architektur)

### 2.1 Modul-Layout

```
src/eaccode/
├── models_dev.py          (NEU, ~400 Zeilen) — Katalog + Cache
├── providers/
│   ├── __init__.py
│   ├── base.py            (NEU, ~100 Zeilen) — StreamChunk, ProviderConfig
│   ├── anthropic.py       (NEU, ~300 Zeilen) — Anthropic SDK-Wrapper
│   ├── openai_compat.py   (NEU, ~250 Zeilen) — OpenAI SDK-Wrapper
│   └── registry.py        (NEU, ~100 Zeilen) — Provider-Auswahl
├── agent.py               (REFACTOR) — nutzt providers.registered()
├── router.py              (REFACTOR oder LÖSCHEN) — ersetzt durch providers/
└── tests/
    ├── test_models_dev.py (NEU)
    ├── test_providers.py  (NEU)
    ├── test_agent.py      (REFACTOR — Mock-Provider statt monkeypatch litellm)
    └── test_palette.py    (REFACTOR — Provider-Stream abstrakter)
```

### 2.2 Was passiert beim Chat-Call

**User tippt `hi` → `ChatApp._submit("hi")` → `Agent.run(messages, on_token=cb)`**

```python
# agent.py (NEU)
class Agent:
    def run(self, messages, on_token=None, ...):
        # 1. Model-Catalog-Hit (aus models.dev Cache)
        model_info = models_dev.get_model_info(self.provider, self.model)
        
        # 2. Provider wählen
        provider = providers.get(self.provider_name)  # anthropic|openai_compat
        
        # 3. Stream-Loop
        for chunk in provider.stream(messages, **kwargs):
            # Chunk hat: {"kind": "text" | "reasoning", "content": str, "tool_calls": [...]}
            on_token(chunk.content, kind=chunk.kind)
            
            # 4. Tool-Calls → Tool-Loop
            if chunk.tool_calls:
                for call in chunk.tool_calls:
                    result = self._execute_tool(call)
                    messages.append({"role": "tool", "content": result, "tool_call_id": call.id})
                # Loop erneut — bis keine tool_calls mehr
```

**Provider-Adapter normalisiert** — egal ob Anthropic-Messages oder OpenAI-Chat-Format, der Agent bekommt **identische StreamChunks**.

### 2.3 Stream-Channel-Schema (NEU)

```python
# providers/base.py
@dataclass
class StreamChunk:
    """Ein Chunk vom Provider, normalisiert."""
    kind: Literal["text", "reasoning", "tool_call", "usage", "done"]
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict | None = None  # {"input_tokens": ..., "output_tokens": ...}
    model: str = ""
```

### 2.4 Konfiguration — was vom User bleibt

`config.yaml` Provider-Format **bleibt gleich** (Hermes verwendet auch dasselbe `providers.X.{api_key, base_url, api_key_env, models}` Schema):

```yaml
providers:
  minimax:
    api_key: sk-cp-...
    base_url: https://api.minimax.io/anthropic  # Anthropic-Adapter triggert
    models: [minimax/MiniMax-M3, ...]
  openrouter:
    api_key_env: OPENROUTER_API_KEY
    base_url: https://openrouter.ai/api/v1  # OpenAI-compat
  anthropic:
    api_key: sk-ant-api-...
    # kein base_url → default Anthropic API
  ollama:
    base_url: http://localhost:11434  # OpenAI-compat
```

**Plus:** `families` Feld pro Provider, das eaccode sagt, ob Anthropic oder OpenAI-Compat benutzt werden soll (default: URL-basiert):

```yaml
providers:
  minimax:
    api_key: ...
    base_url: https://api.minimax.io/anthropic  # → anthropic family
    models: [...]
  # ODER explizit:
  anthropic_family: true  # erlaubt explizite Trennung von URL und Family
```

### 2.5 Was wird NIE mehr getan

- ❌ `litellm.completion(...)` — raus
- ❌ `litellm.suppress_debug_info` — raus
- ❌ OpenAI-Format-Header für MiniMax — raus
- ❌ Willkürliches `reasoning_effort`/`max_tokens`-Default für MiniMax — raus (kommt jetzt aus models.dev)
- ❌ `extra_kwargs` Pass-Through — raus (Provider-Adapter kennen ihre Optionen)

---

## 3. Schritt-für-Schritt (in dieser Reihenfolge)

### Schritt 1 — Dependencies updaten

**Datei:** `pyproject.toml` Z. 11
```toml
# ALT:
"litellm>=1.60",

# NEU:
"anthropic>=0.39",
"openai>=1.60",
"requests>=2.33",
```

**`uv lock` und `uv sync`** laufen lassen.

### Schritt 2 — `models_dev.py` (NEU)

**Datei:** `src/eaccode/models_dev.py` (~400 Zeilen, inspiriert von Hermes)

**Inhalte:**
- `MODELS_DEV_URL = "https://models.dev/api.json"`
- `ModelInfo` dataclass (id, name, family, provider_id, capabilities, context_window, max_output, cost_input, cost_output, ...)
- `ProviderInfo` dataclass (id, name, env, api, doc, model_count)
- `PROVIDER_TO_MODELS_DEV` Mapping (30+ eaccode-Provider → models.dev-IDs)
- `fetch_models_dev(force_refresh, allow_network)` — Cache-Hierarchy: in-mem → disk → network
- `get_model_info(provider, model)` — Returns ModelInfo or None
- `get_provider_info(provider)` — Returns ProviderInfo or None
- `list_provider_models(provider)` — Returns list[str]
- `list_agentic_models(provider)` — Models mit tool-calling
- Disk-Cache: `~/.local/eaccode/models_dev_cache.json`
- Background-Refresh mit Threading.Lock + 5-Min-Backoff

**Differenzen zu Hermes:**
- Cache-Pfad: `~/.local/eaccode/models_dev_cache.json` (nicht `~/.hermes/`)
- **`refresh-retry-after: 5 minutes`** (gleiche Logik)
- In-Memory-TTL: 1 Stunde (wie Hermes)
- **Stale-while-revalidate** für Provider-Existenz-Checks (Hermes-Pattern übernehmen)
- **Hardcoded `provider_id -> models.dev_id` Map entfällt** — Models.dev-Provider-Namen werden direkt genutzt (für MiniMax heißt das `provider.id = "minimax"` → models.dev-Key `"minimax"`)

**Anthropic-SDK-Stream-Verarbeitung (siehe Hermes `chat_completion_helpers.py:3887-3905`):**
- `content_block_start` → Tool-Use oder Thinking-Block sammeln
- `content_block_delta` mit `delta_type == "text_delta"` → `StreamChunk(kind="text", content=delta.text)`
- `content_block_delta` mit `delta_type == "thinking_delta"` → `StreamChunk(kind="reasoning", content=delta.thinking)`
- `message_delta` mit `stop_reason != "end_turn"` → Tool-Loop starten

**Wichtig für MiniMax-M3 (`ctx=1M`):**
- `max_tokens` aus models.dev (`out=128k` für M3), Default nicht hardcoded
- Reasoning-Content immer in eigenem Field (`thinking_delta`), NICHT in `content` mit Token-Markern
- Tool-Calls haben `signature` field (Hermes-M3-Feature) — optional, kann ignoriert werden

**Tests:** `tests/test_models_dev.py` (NEU, ~12 Tests)
- Cache-Hierarchy (in-mem → disk → network)
- Stale-Refresh-Detection
- Provider-Lookup (mit/ohne Treffer)
- Disk-Cache-Persistenz
- Background-Refresh-Backoff
- Network-Failure-Pfad

### Schritt 3 — `providers/` Package (NEU)

**`src/eaccode/providers/__init__.py`** — Public API:
```python
def get(provider_name: str) -> Provider:
    """Return the right provider adapter for the given provider name."""
```

**`src/eaccode/providers/base.py`** — ~100 Zeilen:
- `StreamChunk` dataclass
- `ToolCall` dataclass
- `ProviderConfig` dataclass (api_key, base_url, timeout, model)
- `Provider` ABC mit `stream(messages, **kwargs) -> Iterator[StreamChunk]`

**`src/eaccode/providers/anthropic.py`** — ~300 Zeilen:
- `AnthropicProvider` Klasse
- Baut `anthropic.Anthropic(api_key=..., base_url=..., timeout=..., default_headers=...)`
- Per-Endpoint-Beta-Header-Stripping (für MiniMax):
  - Base-URL `https://api.minimax.io/anthropic` → strip `fine-grained-tool-streaming-2025-05-14`
- Adaptive-Thinking: `thinking={"type": "adaptive", "display": "hidden"}` für Claude 4.6+
- Reasonsing-Content: nutzt `response.message.content` wo jeder Block `{"type": "thinking" | "text", ...}` ist
- Streaming: `client.messages.stream(...)` — iteriert Events, normalisiert zu StreamChunks
- Tool-Calls: aus `input_json_delta` Tool-Use-Blöcken

**`src/eaccode/providers/openai_compat.py`** — ~250 Zeilen:
- `OpenAICompatProvider` Klasse
- Baut `openai.OpenAI(api_key=..., base_url=..., timeout=...)`
- Reasoning: Manche Modelle liefern `delta.reasoning_content`
- Streaming: `client.chat.completions.create(stream=True, ...)`
- Tool-Calls: aus `delta.tool_calls`

**`src/eaccode/providers/registry.py`** — ~100 Zeilen:
- `get_provider_instance(provider_name, conf) -> Provider`
- Family-Detection:
  1. Provider-Name explizit in `anthropic-family` Liste (`anthropic`, `minimax`, `minimax-oauth`, `minimax-cn`)
  2. Base-URL enthält `/anthropic` → Anthropic-Family
  3. Sonst: OpenAI-Compat-Family
- Cache der Provider-Instanzen pro Request

**Tests:** `tests/test_providers.py` (NEU, ~15 Tests)
- AnthropicProvider: Stream-Chunks, Tool-Calls, MiniMax-Header-Stripping
- OpenAICompatProvider: Stream-Chunks, Tool-Calls, Reasoning-Content
- Registry: Family-Detection (URL-basiert, Name-basiert)
- StreamChunk-Dataclass

### Schritt 4 — `agent.py` REFACTOR

**Datei:** `src/eaccode/agent.py`

**Entfernt:**
- `import litellm` (Z. 7)
- `on_token` als optional Callback (bleibt, aber Signatur ändert sich zu `Callable[[StreamChunk], None]`)

**Geändert:**
- `_complete()` → wird zu `_stream_once(provider, messages, **kwargs) -> Iterator[StreamChunk]`
- `run()` → nutzt `providers.get(provider_name)` statt `router._completion_kwargs`
- Iteration: `for chunk in provider.stream(messages, ...)` statt `for chunk in response:`
- Reasoning-Content: kein `reasoning_content`-Field-Handling mehr (Provider-Adapter macht das)
- Tool-Calls: Provider-Adapter liefert `chunk.tool_calls` (nicht mehr LiteLLM-spezifisch)

**Beibehalten:**
- `system_prompt`, `tool_guide`, `MAX_TURNS`, `MAX_OUTPUT_TOKENS`
- `Agent.run(messages, on_token, max_turns, max_output_tokens, cancel_event)`
- ReAct-Loop: bei `tool_calls` → Tool-Execute → Loop erneut, bis keine Calls

**Neu:**
- `agent.py` bekommt `provider_name` und `provider_config` im `__init__`
- `on_token` ist jetzt `Callable[[StreamChunk], None]` (statt `(text: str)`)

### Schritt 5 — `router.py` REFACTOR oder LÖSCHEN

**Datei:** `src/eaccode/router.py`

**Option A (gewählt): Refactor zu `router.py` als "Legacy-Kompatibilitäts-Wrapper"**
```python
# DEPRECATED — use providers.get() instead
def completion_response(...):  # wirft DeprecationWarning
    ...
```

**Option B: LÖSCHEN** + alle Imports aufräumen. Riskanter, weil `agent.py` und `commands.py` darauf zugreifen.

**Gewählt: A** — Refactor mit DeprecationWarning. Spätere Migration auf `providers/`. In 1-2 Sprints raus.

**`router.py` (NEU, ~50 Zeilen):**
- `KNOWN_MODELS` bleibt (für `/model list` UX)
- `model_chain()` bleibt (für Fallback-Kette)
- `completion_response()` und `stream_completion()` → DeprecationWarning + Redirect auf `providers.get()`
- `ping_model()` und `call_model()` bleiben, intern via providers

### Schritt 6 — `palette.py` REFACTOR

**Datei:** `src/eaccode/palette.py`

**Geändert:**
- `_on_token(delta: str, kind: str = "text")` → `_on_token(chunk: StreamChunk)`
- `_strip_think()` wird obsolet (Provider-Adapter macht Reasoning-Stripping)
- `_clean_delta()` bleibt für CR/ANSI-Sanitization
- Reasoning-Rendering bleibt: `[Reasoning: ...]` in italic, dann `]` + neue Zeile + Antwort

**Tests:** `tests/test_palette.py` — alle Mocking-Stellen auf `StreamChunk` umbauen

### Schritt 7 — `cli.py` REFACTOR

**Datei:** `src/eaccode/cli.py`

- `build_agent()` → `providers.get(provider_name)` statt `router._completion_kwargs`
- Keine `litellm`-Imports mehr

### Schritt 8 — Tests REFACTOR

**`tests/test_agent.py`** — 11 `litellm`-Mocks ersetzen durch Provider-Mocks:
```python
# ALT:
monkeypatch.setattr(litellm, "completion", fake_completion)

# NEU:
class FakeAnthropicProvider:
    def stream(self, messages, **kwargs):
        yield StreamChunk(kind="text", content="hi there")
        yield StreamChunk(kind="done")

monkeypatch.setattr(providers, "get", lambda name: FakeAnthropicProvider())
```

**`tests/test_palette.py`** — `on_token`-Mocks umbauen auf `StreamChunk`
**`tests/test_commands.py`** — ähnlich

**Neue Tests:**
- `tests/test_models_dev.py` (~12 Tests)
- `tests/test_providers.py` (~15 Tests)
- `tests/test_providers_anthropic.py` (MiniMax-spezifisch, ~5 Tests)
- `tests/test_providers_openai.py` (OpenRouter, ~5 Tests)

**Gesamt-Tests:** aktuell 467 → nach Refactor ~520

### Schritt 9 — `pyproject.toml` locken

**Datei:** `pyproject.toml`
- `litellm>=1.60` → raus
- `anthropic>=0.39`, `openai>=1.60`, `requests>=2.33` → rein
- `uv lock` synchronisieren

### Schritt 10 — Brain + Doku

**Brain:**
- `brain/15-features/system/model-router.md` — komplett umschreiben (war auf LiteLLM ausgerichtet)
- `brain/15-features/system/agent-core.md` — neuer Block "Provider-Adapter"
- `brain/15-features/system/models-dev.md` (NEU) — Custom Catalog wie Hermes

**Manual-Test:**
- `docs/manual-test.md` — neuer Block "MiniMax via Anthropic-SDK" + "models.dev Catalog"

### Schritt 11 — Live-Verifikation

**User testet manuell:**
- `eaccode config show` → `minimax.base_url` sichtbar
- `eaccode model list` → models.dev Catalog (frisch gefetcht)
- `eaccode` → `hi` → **vollständige Antwort**, kein Abhacken
- `eaccode` → `was kannst du?` → **vollständige Bullet-Liste**
- Reasoning sichtbar als `[Reasoning: ...]` italic
- Tool-Calls funktionieren (`/memory add test`)
- Fallback (`ollama/llama3.2`) greift wenn MiniMax down

---

## 4. Dateien, die sich ändern

| Datei | Art | Zweck |
|---|---|---|
| `pyproject.toml` | Modify | litellm raus, anthropic + openai + requests rein |
| `src/eaccode/models_dev.py` | **NEU** | Model-Catalog |
| `src/eaccode/providers/__init__.py` | **NEU** | Public API |
| `src/eaccode/providers/base.py` | **NEU** | StreamChunk, Provider-ABC |
| `src/eaccode/providers/anthropic.py` | **NEU** | Anthropic-SDK-Wrapper |
| `src/eaccode/providers/openai_compat.py` | **NEU** | OpenAI-SDK-Wrapper |
| `src/eaccode/providers/registry.py` | **NEU** | Provider-Auswahl |
| `src/eaccode/router.py` | Refactor | Deprecation-Wrapper |
| `src/eaccode/agent.py` | Refactor | nutzt providers statt router |
| `src/eaccode/cli.py` | Modify | `build_agent()` nutzt providers |
| `src/eaccode/palette.py` | Modify | `_on_token` nimmt StreamChunk |
| `tests/test_models_dev.py` | **NEU** | models_dev Tests |
| `tests/test_providers.py` | **NEU** | Provider-Tests |
| `tests/test_agent.py` | Refactor | Provider-Mocks |
| `tests/test_palette.py` | Refactor | StreamChunk-Mocks |
| `tests/test_commands.py` | Refactor | Provider-Mocks |
| `brain/15-features/system/model-router.md` | Refactor | models.dev statt LiteLLM |
| `brain/15-features/system/agent-core.md` | Refactor | Provider-Adapter |
| `brain/15-features/system/models-dev.md` | **NEU** | Catalog-Doku |
| `docs/manual-test.md` | Modify | Neue Test-Blocks |

**Nicht ändern:**
- `src/eaccode/banner.py` — UI bleibt
- `src/eaccode/palette.py` Float/Container-Layout — bleibt
- `src/eaccode/cli.py` Argument-Parsing — bleibt
- `src/eaccode/commands.py` Commands wie `/config`, `/memory` — bleiben
- `src/eaccode/permissions.py` — bleibt
- `src/eaccode/store.py` — bleibt

---

## 5. Tests / Validation

### 5.1 Unit
- `pytest tests/test_models_dev.py -v` — 12 neue
- `pytest tests/test_providers.py -v` — 15 neue
- `pytest tests/test_agent.py -v` — Refactor, gleiche Coverage
- `pytest tests/test_palette.py -v` — Refactor, gleiche Coverage
- `pytest -q` — komplette Suite, ~520 passed
- `ruff check .` — sauber

### 5.2 Live
- `eaccode config show` → MiniMax mit `base_url: https://api.minimax.io/anthropic`
- `eaccode model list` → models.dev Catalog (5000+ Models)
- `eaccode model ping minimax/MiniMax-M3` → `pong` (Reasoning + Antwort)
- `eaccode` → `hi` → **vollständige Antwort** (nicht abgeschnitten)
- `eaccode` → `was kannst du?` → **vollständige Bullet-Liste**
- Reasoning in `[Reasoning: ...]` italic sichtbar
- Tool-Calls funktionieren (`/memory add test`)
- Fallback (`ollama/llama3.2`) greift bei MiniMax-Ausfall

### 5.3 Regressions
- Alle bestehenden 467 Tests müssen weiter grün sein
- Slash-Palette, Banner, Auth, Permissions — keine Änderung

---

## 6. Klärungen (User-Antworten)

1. **Plan freigegeben:** ✓ nach Klärung
2. **Anthropic SDK Version:** `anthropic==0.87.0` (Hermes-pinned, CVE-safe)
3. **OpenAI SDK Version:** `requests==2.33.0` (Hermes-pinned, CVE-safe) — **kein OpenAI SDK** (nur MiniMax via Anthropic-SDK)
4. **Anthropic-Compatible Scope:** **Nur MiniMax** im ersten Schritt. Andere Provider später.
5. **Ollama:** **Raus** — wenn MiniMax down ist, crashed eaccode. Reines Testing-Setup.

## 7. Konsequenzen aus den Klärungen

- **Kein OpenAI SDK** im ersten Schritt → `providers/openai_compat.py` ENTFÄLLT komplett
- **Nur Anthropic SDK** für `providers/anthropic.py` (~300 Zeilen)
- **Ollama-Fallback** raus → `KNOWN_MODELS["ollama"]` löschen, Fallback-Kette leer
- **Aufwand sinkt deutlich** weil nur 1 Provider-Adapter geschrieben werden muss

## 8. Models.dev-Insights (live heute abgefragt)

```
models.dev für MiniMax:
  provider.name: "MiniMax (minimax.io)"
  provider.env: ["MINIMAX_API_KEY"]
  provider.api: https://api.minimax.io/anthropic/v1
  provider.doc: https://platform.minimax.io/docs/guides/quickstart
  Models: 7 (M3, M2.7, M2.7-highspeed, M2.5, M2.5-highspeed, M2.1, M2)
  MiniMax-M3: ctx=1M, out=128k, cost=$0.3/$1.2/M, reasoning=True, tool_call=True
  Andere:    ctx=204.8k, out=131.072k, gleiche Preise
```

**Wichtig:** M3 hat **1M Context**, alle anderen **204.8k**. `max_output` ist 128k/131k je nach Model — models.dev hat die alle.

## 9. Streaming-Insights (Hermes-Code-Studium)

**Anthropic-Messages-Stream (was MiniMax-M3 zurückgibt):**
- `event_type == "content_block_start"` → Tool-Use-Block oder Thinking-Block
- `event_type == "content_block_delta"` mit `delta_type == "text_delta"` → Text, `delta.text`
- `event_type == "content_block_delta"` mit `delta_type == "thinking_delta"` → Reasoning, `delta.thinking`
- `event_type == "message_delta"` mit `stop_reason` → Tool-Use oder End-Block

**Hermes' Anwendungs-Schema:**
- Zwei CALLBACKS: `agent._fire_stream_delta(text)` für Text, `agent._fire_reasoning_delta(thinking_text)` für Reasoning
- Reasoning kommt in **eigenem Field**, nicht in `content` gemischt
- Tool-Use-Blöcke kommen als `content_block_start` mit `block.type == "tool_use"`

**Mein eaccode-Adapter muss:**
- Auf `content_block_delta` lauschen
- Bei `delta_type == "text_delta"` → `StreamChunk(kind="text", content=...)`
- Bei `delta_type == "thinking_delta"` → `StreamChunk(kind="reasoning", content=...)`
- Bei `content_block_start` mit `block.type == "tool_use"` → Tool-Call sammeln
- Bei `message_delta` mit `stop_reason != "end_turn"` → Tool-Use-Loop triggern

## 10. Out-of-Scope (bleibt)

- ❌ OAuth-Setup-Tokens (Hermes hat `sk-ant-oat*`)
- ❌ Bedrock/Azure Anthropic-Messages-Wrapper
- ❌ Claude Code Identity Spoofing
- ❌ 1M-Context-Beta-Header
- ❌ Cost-Tracking via Cache-Hits
- ❌ Reasoning-Effort-Mapping (Claude 4.6+ levels)
- ❌ Adaptive-Thinking (Claude 4.6+)

**Falls du eins davon willst:** Separater Plan.

---

## 8. Aufwand & Reihenfolge

| # | Schritt | Dauer | Commit |
|---|---|---|---|
| 1 | `pyproject.toml` deps | 5 min | `chore: drop litellm, add anthropic+requests` |
| 2 | `models_dev.py` + Tests | 2 h | `feat(models-dev): catalog + cache` |
| 3 | `providers/anthropic.py` + Tests | 2.5 h | `feat(providers): anthropic adapter (MiniMax)` |
| 4 | `providers/registry.py` + `__init__.py` | 1 h | `feat(providers): registry with family detection` |
| 5 | `agent.py` Refactor | 1.5 h | `refactor(agent): use anthropic provider instead of litellm` |
| 6 | `router.py` → Deprecation-Wrapper | 20 min | `refactor(router): deprecation wrapper to providers` |
| 7 | `palette.py` `_on_token` StreamChunk | 30 min | `refactor(chat): on_token takes StreamChunk` |
| 8 | `cli.py` build_agent | 10 min | `chore(cli): build_agent uses providers` |
| 9 | Tests refactor | 1.5 h | `test(providers): full coverage + mocks` |
| 10 | `KNOWN_MODELS` + Ollama raus | 10 min | `chore: drop ollama from KNOWN_MODELS` |
| 11 | Brain + Doku | 30 min | `docs(providers): catalog + adapters` |
| 12 | Live-Verifikation | 20 min | (manuell durch User) |

**Gesamt: ~10 Stunden, 8-10 Commits.**

Das ist **viel**, aber **einmal richtig** statt weitere LiteLLM-Patches, die das Problem nicht lösen.

---

## 9. Status

**`DRAFT`** — wartet auf User-Freigabe. Fragen in Sektion 6.
