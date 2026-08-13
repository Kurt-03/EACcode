# Projekte — Dashboard

Aktive Arbeitsstränge und offene Entscheidungen. *(Pointer: aktueller Code-
und Teststand liegt im Repo — `C:\Projekte\EACcode V3`.)*

## Aktive Phase: C — Production-Reife (2026-08-13)

**Fortschritt:** C1 Permissions ✅ · C2 Cron/Daemon ✅ · C3 MCP ✅ · C4 Gateway ⏳ · C5 Packaging ⏳
→ Ziel: sicher, autonom, verteilbar. DoD: installierbar auf 3 OS, Cron→Telegram, MCP-Tool genutzt, Permission-Regeln wirken.

## Abgeschlossen

- **Phase A — Foundation & MVP ✅** (2026-08-13) → [[50-archive/phase-a.md|Phase A]]

## Offene Entscheidungen

- [ ] **O2 — Provider-Erstauslieferung:** MiniMax + opencode-go (bekannt) vs.
      OpenRouter-first vs. Ollama-first → vor Phase A3-Nacharbeit / B
- [ ] **O3 — Display-Name / Identität:** CLI heißt `eaccode` — Produktname/Claim?
- [ ] **O4 — Dev-Python:** via uv 3.12+ (Tool-Venv läuft aktuell mit 3.14)
- [ ] **Slash-Commands anpassen** *(2026-08-13 vom User angemerkt, Details offen)*
      — die `/`-Befehle sollen überarbeitet werden; Zeitpunkt: passend in B/C,
      Details dann mit dem User konkretisieren

## Ideen-Backlog (aus dem Brain-Umbau übernommen)

- [ ] GUI als spätere Oberfläche (CLI-first bleibt gesetzt)
- [ ] Gateway-Reihenfolge: Telegram → Discord/Slack/WhatsApp (Phase C)
- [ ] TUI: `/copy` bei Maus-Selektion, Hermes-Style-Glyphen, Fuzzy-Slash-Overlay
- [ ] eaccode soll diesen Brain ab Phase B selbst lesen und pflegen können
- [ ] Auto-Update für die installierte exe (`eaccode update`)
