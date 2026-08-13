# eaccode

Self-improving generalist agent — **Hermes-inspired orchestration** (persistent
memory, skill learning loop, autonomy, cron) with **Claude-Code-level coding**
as one capability.

- **BYOK** — bring your own keys: OpenAI-compatible and native providers
  (Anthropic, Google, xAI, DeepSeek, OpenRouter, Ollama, vLLM, …) via LiteLLM
- **Local & cross-platform** — Windows, Linux, macOS; no cloud required
- **Self-improving** — agent-curated memory and automatic skill creation
- **Generalist** — coding is one strong capability, not the whole product
- **MIT licensed** — keys belong to you, data stays on your machine

## Status

Early development — Phase A (Foundation & MVP) of the master plan
(`.hermes/plans/2026-08-13_130000-eaccode-v2-master-plan.md`).

## Development

```bash
uv sync             # create venv + lockfile
uv run pytest       # run the test suite
uv run ruff check   # lint
uv run eaccode --version
```
