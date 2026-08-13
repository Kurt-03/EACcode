# Commands-Index — jeder `/command` einzeln dokumentiert

Jeder Slash-Befehl hat eine eigene Notiz (Zweck, Syntax, Beispiele,
Implementierung, Tests). **Neue Commands → eigene Notiz + Zeile hier.**

| Command | Zweck | Status | Notiz |
|---|---|---|---|
| `/help` | Befehlsübersicht | done (A1) | [[15-features/commands/help.md\|help]] |
| `/version` | Version anzeigen | done (A1) | [[15-features/commands/version.md\|version]] |
| `/clear` | Bildschirm + Chat-History leeren | done (A7) | [[15-features/commands/clear.md\|clear]] |
| `/exit` | Session beenden (Alias `/quit`) | done (A1) | [[15-features/commands/exit.md\|exit]] |
| `/config` | Config verwalten (8 Sub-Commands) | done (A2) | [[15-features/commands/config.md\|config]] |
| `/provider` | Provider verwalten (5 Sub-Commands) | done (A3) | [[15-features/commands/provider.md\|provider]] |
| `/model` | Modelle verwalten (5 Sub-Commands) | done (A3) | [[15-features/commands/model.md\|model]] |
| `/memory` | Memory verwalten (4 Sub-Commands) | done (A6) | [[15-features/commands/memory.md\|memory]] |
| `/skill` | Skills verwalten (4 Sub-Commands) | done (B1) | [[15-features/commands/skill.md\|skill]] |
| `/session` | Session-Suche (FTS5) | done (B3) | [[15-features/commands/session.md\|session]] |
| `/job` | Jobs verwalten (list/add/run) | done (C2) | [[15-features/commands/job.md\|job]] |
| `/mcp` | MCP-Server (list/add/import) | done (C3) | [[15-features/commands/mcp.md\|mcp]] |
| `/permissions` | Modi + Regeln | done (C1) | [[15-features/commands/permissions.md\|permissions]] |
| `/tui`-Start | `eaccode tui` startet die TUI | done (A8) | [[15-features/commands/tui.md\|tui]] |

*Stand: 2026-08-13 — 13 Commands aktiv, alle mit eigener Notiz*

## Code-Graph (generiert)

- `src/eaccode/commands.py` → [[15-features/system/config.md|config.yaml]] · [[15-features/system/cron-daemon.md|cron-daemon]] · [[15-features/system/memory.md|Memory]] · [[15-features/system/permissions.md|permissions]] · [[15-features/system/model-router.md|Model Router]] · [[15-features/system/skill-system.md|skill-system]] · [[15-features/system/session-store.md|session-store]]

