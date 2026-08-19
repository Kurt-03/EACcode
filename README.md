# eaccode

Self-improving generalist agent — **Hermes-inspired orchestration** (persistent
memory, skill learning loop, autonomy, cron) with **Claude-Code-level coding**
as one capability.

- **BYOK** — bring your own keys: OpenAI-compatible (OpenAI, OpenRouter, Ollama,
  vLLM, DeepSeek, Groq, xAI, OpenCode Zen) and Anthropic-Messages-compatible
  (Anthropic, MiniMax)
- **Local & cross-platform** — Windows, Linux, macOS; no cloud required
- **Self-improving** — agent-curated memory and automatic skill creation
- **Generalist** — coding is one strong capability, not the whole product
- **MIT licensed** — keys belong to you, data stays on your machine

## Honest Status (as of 2026-08-18)

eaccode has a real shell tool (`run_command`), configurable budgets
(`MAX_TURNS=50`, `max_output_tokens=4096`), OpenAI + Anthropic provider
adapters, auto-compaction when the context window fills up, a todo
tool, plan-mode, diff-preview + persistent undo, real ripgrep-backed
search, an AST-based repo-graph, and an OpenCode-Zen-friendly
permissions layer.

What's **not** there yet:
- Thread-safety is partial (workspace + todo + undo are protected, but
  permission-handler is still module-global — see Plan I P2.12 backlog).
- Plan-mode and Todo are wired as modules, but not yet surfaced as
  slash-commands (``/plan``, ``/todo``) or auto-injected into the
  agent loop. They work if you call the tool directly.
- Semantic skill-matching (Plan I P3.14) needs an embedding model and
  is **not** done.
- Provider tests don't include a live OpenAI smoke test (we don't
  ship your API key into CI).

What it **does not** claim:
- It is **not** "Claude Code rewritten in Python". It's a smaller,
  Hermes-flavoured agent. Use it for what it's good at; don't expect
  parity on hundreds of turns of refactor.
- The README used to claim LiteLLM / Google / Mistral / OpenRouter
  through a single dispatcher — that's no longer true. The current
  implementation has one Anthropic adapter and one OpenAI-compat
  adapter. The OpenAI-compat adapter covers OpenRouter, Ollama, vLLM,
  DeepSeek, Groq, xAI, OpenCode Zen. Mistral + Google were dropped in
  the Plan A refactor.

## Development

```bash
uv sync              # create venv + lockfile
uv run pytest        # run the test suite (1083 tests)
uv run ruff check    # lint
uv run eaccode --version
```

## Run

```bash
# REPL
eaccode

# One-shot
eaccode -p "run pytest"

# Plan I budgets
eaccode -p "refactor foo to bar" --max-turns 100 --max-tokens 8192
```

## Configuration

`~/.local/share/eaccode/config.yaml` (created on first run):

```yaml
model:
  default: opencode-zen/your-model
  fallback:
    - openai/gpt-4

providers:
  openai:
    api_key_env: OPENAI_API_KEY
  opencode-zen:
    api_key_env: OPENCODE_ZEN_API_KEY
    base_url: https://api.opencode.ai/zen/v1

permissions:
  mode: smart     # off | manual | smart | plan

agent:
  max_turns: 50
  max_output_tokens: 4096
```

API keys are read from environment variables (``api_key_env``) -
never store them in config.yaml.
