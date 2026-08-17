# MiniMax-M3 Provider-Setup & Stream-Bereinigung — Plan

> **Status:** `DRAFT` — wartet auf User-Freigabe. User-Hinweis: "schau bei Hermes nach, was an MiniMax fehlt".
> **Quellen:** `src/eaccode/router.py`, `C:/Projekte/_ref/hermes/agent/*.py`, Live-Test der API.

**Goal:** Drei Probleme zusammen lösen, die Antworten von MiniMax-M3 abhacken oder verfremden:
1. **Provider-Setup unvollständig** — `minimax/MiniMax-M3` funktioniert über LiteLLMs `minimax`-Provider, aber eaccode hat keine `base_url`, kein `api_key_env`, keine `reasoning_effort`-Spezialbehandlung.
2. **Stream-Filter zu fragil** — `_strip_think` in `src/eaccode/palette.py` filtert `Reasoning`-Blöcke aus dem gestreamten Content. Aber:
   - Tag-Splits über Chunk-Boundaries werden teils richtig, teils falsch behandelt
   - Manche Provider trennen **Reasoning** in eigenes `delta.reasoning_content`-Feld (Moonshot, Novita, ggf. MiniMax via Anthropic-Adapter)
   - LiteLLM hat einen eingebauten `reasoning_content`-Filter (`drop_params=True` würde helfen, aber auch andere Felder weglassen)
3. **LiteLLM-Kwargs ohne Reasoning-Settings** — `extra_kwargs` hat nur `max_tokens` + `tools`, kein `reasoning_effort`, kein `cache_control`, etc.

**Architecture:** Drei punktuelle Änderungen, alle mit TDD (Tests für jeden Fix).

**Tech Stack:** Python 3.12+, `litellm` (1.60+), `pyyaml`, `prompt_toolkit`.

---

## 1. Was ist kaputt (Diagnose)

### 1.1 Provider-Setup ist lückenhaft

**User-Config (geladen via `eaccode config show`):**
```yaml
providers:
  minimax:
    api_key: sk-***
  # KEIN base_url
  # KEIN api_key_env
  # KEIN models-Block
```

**LiteLLM macht daraus:**
- `_completion_kwargs`: `model="minimax/MiniMax-M3"`, `api_key=sk-...`, **kein `api_base`**
- LiteLLM erkennt `minimax` als Provider (laut `litellm.provider_list`) und routet auf eine **Default-URL**
- `minimax-MiniMax-M3` ist im Cost-Map mit `supports_reasoning: True`, `max_input_tokens: 1M`, `max_output_tokens: 128000`

**Hermes macht es anders:**
- `agent_runtime_helpers.py:665-670` — liest `reasoning_content` aus dem **Assistant-Message**-Objekt
- `agent_runtime_helpers.py:1760-1779` — trennt `reasoning_content` (Standard) von `reasoning_content` (alternative Feldnamen)
- `auxiliary_client.py:8010` — `_ANTHROPIC_COMPAT_PROVIDERS = frozenset({"minimax", "minimax-oauth", "minimax-cn"})` → MiniMax erwartet **Anthropic-Format** bei Content-Blöcken
- `agent_runtime_helpers.py` Z. 3883: "MiniMax provider on Anthropic-wire (api.minimax.io/anthropic / api.minimaxi.com/anthropic)" → cache_control markers wirken
- `auxiliary_client.py:8190` — "minimaxai/minimax-m3" → NVIDIA NIM-Endpoint, `max_tokens` MUSS gesetzt sein, sonst HTTP 200 mit leerem choices[]

**Mein eaccode hat von all dem NICHTS.** LiteLLM fällt auf Default-OpenAI-kompatibel zurück (wahrscheinlich `https://api.minimax.io/v1/chat/completions`).

### 1.2 Stream-Filter ist zu fragil

**Test mit echtem MiniMax-M3 (ausgeführt heute, 19:18):**
```
chunk 0: 'The user said'
chunk 1: ' "Reply in exactly'
chunk 2: ' 5 words."'
chunk 3: " That's"
chunk 4: ' a very short'
chunk 5: ' prompt'
chunk 6: ' with'
chunk 7: ' no specific question'
chunk 8: ' or topic'
chunk 9: '. I need'
```

**Was fehlt:** Reasoning-Marker `` am Anfang (weggefiltert) — gut. Aber **die letzten reasoning-Token werden mit der Antwort vermischt**, weil `<TAGS>`-Ende und Antwort-Anfang über Chunk-Boundaries splitten.

**Mein `_strip_think` (fix gestern):**
```python
if self._think_buffer:
    self._think_buffer += text
    if THINK_CLOSE in self._think_buffer:
        _, _, rest = self._think_buffer.partition(THINK_CLOSE)
        self._think_buffer = ""
        return rest
    return ""
```

**Problem:** Wenn `text` über mehrere Chunks gesplittet ist und `THINK_CLOSE` erst **nach** der Antwort kommt, schnappt sich mein Filter die **Antwort** in `_think_buffer` und wartet auf `THINK_CLOSE`. Wenn die nächsten Chunks KEIN `THINK_CLOSE` mehr enthalten (Stream ist zu Ende), wird `_think_buffer` verworfen → **die Antwort verschwindet komplett**.

**Symptom:** Du siehst Antworten wie "?", einzelne Wörter, oder nur den Anfang von Sätzen.

### 1.3 Kein `reasoning_content`-Field-Handling

**LiteLLM hat zwei Felder:**
- `delta.content` — Standard-Stream-Content (kann `<TAGS>` enthalten)
- `delta.reasoning_content` — Separates Feld (manche Provider, z.B. Moonshot, Novita)

**Mein Code (router.py → agent.py `_complete`):**
```python
delta = chunk.choices[0].delta
text = getattr(delta, "content", None)
if text:
    content_parts.append(text)
    on_token(text)
```

**Wenn** MiniMax-M3 Reasoning als `reasoning_content` sendet (manche Provider-Setup), wird **die Antwort NULL** weil `content` leer ist. Wenn LiteLLM cached/filtert, kommt es nochmal zu Verschiebungen.

---

## 2. Soll-Bild (konkret, mit Code)

### 2.1 Provider-Setup (config.yaml)

```yaml
providers:
  minimax:
    api_key: sk-***
    base_url: https://api.minimax.io/anthropic  # Anthropic-kompatibler Endpunkt
    # Optional: api_key_env: MINIMAX_API_KEY  # wenn env-basiert gewünscht
    models:
      - minimax/MiniMax-M3
      - minimax/MiniMax-M2.5
      - minimax/MiniMax-M2.1
  openrouter:
    api_key_env: OPENROUTER_API_KEY
  ollama:
    base_url: http://localhost:11434
```

**MiniMax bekommt `base_url`** — LiteLLM routet automatisch auf Anthropic-kompatiblen Endpunkt. Reasoning-Marker werden vom Provider selbst verwaltet, LiteLLM transparent weitergereicht.

### 2.2 Stream-Filter (ChatApp)

**Neue Logik in `src/eaccode/palette.py`:**

```python
def _strip_think(self, text: str) -> str:
    """Filter reasoning tags. Streams answer via different channels:
    - LiteLLM sometimes separates reasoning into delta.reasoning_content
    - The model may emit  reasoning in delta.content with <TAGS> markers
    - Sub-stream may arrive split across chunks
    """
    if self._think_buffer:
        # Reasoning already in flight; keep accumulating
        self._think_buffer += text
        if THINK_CLOSE in self._think_buffer:
            # End of reasoning; return everything AFTER the close tag
            _, _, rest = self._think_buffer.partition(THINK_CLOSE)
            self._think_buffer = ""
            return rest
        # No close tag yet — buffer it, don't show
        return ""
    if THINK_OPEN in text:
        # First time we see the open tag
        before, _, after = text.partition(THINK_OPEN)
        if THINK_CLOSE in after:
            # Both tags in the same chunk
            _, _, rest = after.partition(THINK_CLOSE)
            return before + rest
        # Open tag without close tag — buffer everything from the open tag
        self._think_buffer = text[text.index(THINK_OPEN):]
        return before
    # No tag at all — pass through
    return text
```

**Plus Bug-Fix:** Wenn `on_token` mit leerem delta kommt (Stream-Ende), muss `_think_buffer` **verworfen** werden, statt zu leak'en. In `_agent_worker` (Z. 401-408):

```python
self._stream_open = False
if self._streamed_any:
    print()
elif answer:
    self._emit(answer)
# NEU: Falls noch was im Think-Buffer ist (Stream endete mitten im Reasoning),
# wird der verworfen — wir behalten die finale Antwort aus `last_text()`.
self._think_buffer = ""
```

### 2.3 Routing: Reasoning-Field Support

**`src/eaccode/agent.py` `_complete` (Z. 157-193):**

```python
for chunk in response:
    if not getattr(chunk, "choices", None):
        continue
    delta = chunk.choices[0].delta
    # BOTH fields: some providers send reasoning in delta.reasoning_content
    # (Moonshot, Novita, some MiniMax setups); others inline in delta.content
    reasoning_text = getattr(delta, "reasoning_content", None)
    text = getattr(delta, "content", None)
    if text:
        # Filter reasoning tags of inline content (miniMax pattern)
        filtered = filter_think_tags(text)
        if filtered:
            content_parts.append(filtered)
            on_token(filtered)
    # Note: reasoning_content is dropped silently — UI doesn't show reasoning
```

**Note für später:** Falls wir Reasoning dem User zeigen wollen (Hermes tut das), brauchen wir ein eigenes Reasoning-Channel im UI. Out of scope hier.

### 2.4 Router: `reasoning_effort` und andere MiniMax-Settings

**`src/eaccode/router.py` `_completion_kwargs` (Z. 91-109):**

```python
def _completion_kwargs(
    model_id: str,
    messages: list[dict[str, str]],
    conf: dict[str, Any],
    timeout: float,
    extra_kwargs: dict[str, Any] | None,
) -> dict[str, Any]:
    provider_name = model_id.split("/", 1)[0]
    provider = (conf.get("providers") or {}).get(provider_name)
    api_key = resolve_api_key(provider)
    
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "timeout": timeout,
    }
    
    # MiniMax-M3: max_tokens MUSS gesetzt sein (sonst leerer choices[])
    if provider_name == "minimax" and "max_tokens" not in (extra_kwargs or {}):
        kwargs["max_tokens"] = 4096  # Default für MiniMax-M3 (1M context, 128k output)
    
    if extra_kwargs:
        kwargs.update(extra_kwargs)
    if api_key:
        kwargs["api_key"] = api_key
    if provider and provider.get("base_url"):
        kwargs["api_base"] = provider["base_url"]
    return kwargs
```

**`src/eaccode/router.py` `KNOWN_MODELS` (Z. 16-32):**

```python
KNOWN_MODELS: dict[str, list[str]] = {
    # ... existing ...
    "minimax": [
        "minimax/MiniMax-M3",
        "minimax/MiniMax-M2.5",
        "minimax/MiniMax-M2.1",
        "minimax/MiniMax-M2.1-lightning",
    ],
    # ... rest ...
}
```

---

## 3. Schritt-für-Schritt

### Schritt 1 — Provider-Config hinzufügen

**Datei:** `src/eaccode/config.py` (kein Code-Change, nur Doku).
**Datei:** `src/eaccode/commands.py` (`/provider add` kann jetzt `base_url` und `models` setzen).

**action:** `provider add minimax --base-url https://api.minimax.io/anthropic`

### Schritt 2 — `KNOWN_MODELS` erweitern

**Datei:** `src/eaccode/router.py`

```python
KNOWN_MODELS: dict[str, list[str]] = {
    "minimax": [
        "minimax/MiniMax-M3",
        "minimax/MiniMax-M2.5",
        "minimax/MiniMax-M2.1",
        "minimax/MiniMax-M2.1-lightning",
    ],
    # ...
}
```

### Schritt 3 — `max_tokens`-Default für MiniMax

**Datei:** `src/eaccode/router.py` `_completion_kwargs`

```python
def _completion_kwargs(...):
    ...
    provider_name = model_id.split("/", 1)[0]
    ...
    if provider_name == "minimax" and "max_tokens" not in (extra_kwargs or {}):
        kwargs["max_tokens"] = 4096
    ...
```

### Schritt 4 — `reasoning_content` Field-Support

**Datei:** `src/eaccode/agent.py` `_complete`

```python
for chunk in response:
    if not getattr(chunk, "choices", None):
        continue
    delta = chunk.choices[0].delta
    text = getattr(delta, "content", None)
    if text:
        content_parts.append(text)
        on_token(text)
    # Neuer Fall: manche Provider senden Reasoning separat
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        # Reasoning nicht in den Stream schicken — der User-Filter
        # _strip_think würde es sowieso nicht sehen
        pass
```

### Schritt 5 — Stream-Filter härten

**Datei:** `src/eaccode/palette.py` `_agent_worker`

```python
self._stream_open = False
if self._streamed_any:
    print()
elif answer:
    self._emit(answer)
# NEU: Verworfen-Reste vom Think-Buffer am Stream-Ende
self._think_buffer = ""
```

### Schritt 6 — Tests

**Datei:** `tests/test_router.py` (neu) und `tests/test_palette.py` (erweitert)

```python
# tests/test_router.py
class TestProviderSetup:
    def test_minimax_default_max_tokens(self) -> None:
        """MiniMax-M3 needs max_tokens, otherwise it returns empty choices."""
        conf = {"providers": {"minimax": {"api_key": "sk-fake"}}}
        kwargs = router._completion_kwargs(
            "minimax/MiniMax-M3",
            [{"role": "user", "content": "hi"}],
            conf, 30.0, None,
        )
        assert kwargs["max_tokens"] == 4096

    def test_minimax_base_url_propagation(self) -> None:
        """base_url from config is passed to LiteLLM."""
        conf = {"providers": {"minimax": {
            "api_key": "sk-fake",
            "base_url": "https://api.minimax.io/anthropic",
        }}}
        kwargs = router._completion_kwargs(
            "minimax/MiniMax-M3",
            [{"role": "user", "content": "hi"}],
            conf, 30.0, None,
        )
        assert kwargs["api_base"] == "https://api.minimax.io/anthropic"

    def test_minimax_explicit_max_tokens_not_overridden(self) -> None:
        """Caller can still override max_tokens."""
        conf = {"providers": {"minimax": {"api_key": "sk-fake"}}}
        kwargs = router._completion_kwargs(
            "minimax/MiniMax-M3",
            [{"role": "user", "content": "hi"}],
            conf, 30.0, {"max_tokens": 100},
        )
        assert kwargs["max_tokens"] == 100

# tests/test_palette.py (Erweiterung)
class TestStreamEndthinkBufferReset:
    def test_think_buffer_reset_at_stream_end(self) -> None:
        """If stream ends inside a think block, the buffer is discarded."""
        app = palette.ChatApp(agent=...)
        app._think_buffer = "leftover"
        # Simulate end of stream
        app._emit("")  # would be done by agent_worker
        assert app._think_buffer == ""  # reset
```

### Schritt 7 — Doku

**Brain:** `brain/15-features/system/stream-filter.md` (neu) — dokumentiert die Stream-Bereinigungs-Pipeline. `brain/15-features/system/repl.md` — Update mit Reasoning-Settings. 

**Manual-Test:** `docs/manual-test.md` — neuer Block "MiniMax Provider Setup" mit:
- `provider add minimax --base-url ...`
- `model set-default minimax/MiniMax-M3`
- Live-Test: `hi` → vollständige Antwort, kein Abhacken

---

## 4. Was ich vom User brauche

1. **MiniMax-Account bestätigen:** Hat der User einen **Anthropic-kompatiblen** Account (mit `api.minimax.io/anthropic` Zugang) oder nur OpenAI-kompatiblen? Das bestimmt die `base_url`.
2. **Reasoning zeigen:** Soll der User den Reasoning-Output im UI sehen (Hermes-Stil) oder ist es okay, wenn Reasoning komplett verschluckt wird? Aktueller Plan: Reasoning wird verschluckt (kein UI-Change).
3. **Fallback-Kette:** Aktuell ist `ollama/llama3.2` der Fallback. Soll das so bleiben, oder soll ich auch Anthropic-kompatible Fallbacks (z.B. `openrouter/anthropic/claude-sonnet-4`) hinzufügen?

---

## 5. Dateien, die sich ändern

| Datei | Art | Zweck |
|---|---|---|
| `src/eaccode/router.py` | Modify | `KNOWN_MODELS` + `max_tokens`-Default + `base_url`-Propagierung |
| `src/eaccode/agent.py` | Modify | `reasoning_content`-Field-Support in `_complete` |
| `src/eaccode/palette.py` | Modify | `_think_buffer`-Reset am Stream-Ende |
| `src/eaccode/commands.py` | Modify | `provider add` um `--base-url` und `models` erweitern |
| `tests/test_router.py` | New | Provider-Setup-Tests |
| `tests/test_palette.py` | Modify | Stream-Reset-Test |
| `brain/15-features/system/stream-filter.md` | New | Doku |
| `docs/manual-test.md` | Modify | MiniMax-Setup-Test |

**Nicht ändern:**
- `src/eaccode/banner.py` — Banner bleibt
- `src/eaccode/cli.py` — kein Touch (außer via `/provider add`)
- `src/eaccode/repl.py` — Stream-Loop bleibt

---

## 6. Test-Plan

### 6.1 Unit
- `pytest tests/test_router.py -v` — Provider-Setup
- `pytest tests/test_palette.py -v` — Stream-Reset
- `pytest tests/test_agent.py -v` — Reasoning-Content-Handling
- `pytest` — alle 467+ Tests grün

### 6.2 Live-Verifikation
- `eaccode config init` einmalig
- `provider add minimax --base-url https://api.minimax.io/anthropic`
- `provider set-key minimax` (oder via env)
- `model set-default minimax/MiniMax-M3`
- `eaccode` starten
- `hi` senden → vollständige Antwort, **nicht** mitten im Satz abgeschnitten
- `was kannst du?` → vollständige Bulletliste

### 6.3 Regressions
- Stream-Test mit Mock (kein API-Call) — die Tests in `test_palette.py::TestStreamStripThink` decken den Filter ab
- Andere Provider (OpenRouter, Ollama) müssen unverändert funktionieren

---

## 7. Out-of-Scope

- Reasoning-UI-Channel (User kann denken-Tokens sehen)
- Prompt-Caching konfigurieren
- Vision / Multimodalitäten
- Spezielle MiniMax-Features (audio, video)

---

## 8. Aufwand

| # | Schritt | Dauer |
|---|---|---|
| 1 | Provider-Config | 2 min |
| 2 | KNOWN_MODELS | 1 min |
| 3 | max_tokens-Default | 3 min |
| 4 | reasoning_content | 5 min |
| 5 | Stream-Reset | 3 min |
| 6 | Tests | 15 min |
| 7 | Docs | 5 min |
| 8 | Live-Test | 10 min |

**Gesamt: ~45 min.**

---

## 9. Status

**`DRAFT`** — wartet auf User-Freigabe. Fragen in Sektion 4.
