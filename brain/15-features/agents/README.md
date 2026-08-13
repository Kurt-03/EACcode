# Agents

Subagenten-Features und Agent-Architektur.

## Subagents ✅ (Phase B5, gebaut)

- Feature-Notiz: [[15-features/system/subagents.md|subagents]]
- Pool max. 6 parallel, Tool-Restriktion, Timeout-Cancel, Reasoning-only
- Ergebnisse werden im Session-Store geloggt (tool-Messages)
- Live verifiziert: 2 Subagents parallel, Fehler-Isolation

## Weitere Agent-Themen

- [[15-features/system/agent-core.md|Agent Core]] — ReAct-Loop, Tools,
  parallele Ausführung, Memory-Nudge, Skill-Injection
- [[15-features/system/learning-loop.md|learning-loop]] — Skill-Erstellung
  durch den Agenten selbst
