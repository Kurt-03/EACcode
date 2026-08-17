"""Provider adapters for eaccode.

Public API:
    get(provider_name: str, conf: dict) -> Provider

Each adapter normalizes the wire format (Anthropic Messages, OpenAI Chat
Completions, ...) into a common ``StreamChunk`` shape so the agent does
not need to know which provider families the underlying SDK uses.

Currently only the Anthropic-compatible adapter is implemented. OpenAI-compat
providers (Ollama, etc.) are out of scope for the first cut.
"""
