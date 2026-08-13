---
name: browser
type: system
status: done
phase: D6
date: 2026-08-13
tags: [type/feature, feature/system]
---

# System: Browser-Automation (D6)

## Zweck
Der Agent steuert einen headless Chromium: navigieren, klicken, tippen,
Text extrahieren, Screenshots — mit Session-Persistenz über mehrere Calls.

## Implementierung
- `src/eaccode/browser.py` — `BrowserSession` (lazy Launch, RLock für
  Thread-Sicherheit im Parallel-Loop, atexit-Close), Tools:
  `browser_navigate/click/type/extract/screenshot/status`
- Dependency: `playwright>=1.40` + `playwright install chromium` (einmalig)
- Mutierend → läuft durch den Permission-Gate (ask)

## Verifiziert (live, 2026-08-13)
- Agent öffnete example.com, extrahierte h1 + ersten Absatz (echte Antwort)
- `browser_screenshot` erzeugte PNG (4714 B)
- Tests gegen echte file://-Seiten (navigate/extract/type/click/screenshot)

## Tests
`tests/test_browser.py` (7, inkl. echte Chromium-Integration, skip ohne Browser)

## Offene Punkte
- `browser_navigate` vor Screenshot nötig (leere Session = about:blank)
- Mehrere Tabs/Contexts — bei Bedarf

## Verknüpft
[[15-features/README.md|Feature-Register]] · [[15-features/system/permissions.md|permissions]] · [[15-features/system/agent-core.md|Agent Core]]

## Code-Graph (generiert)

- `src/eaccode/browser.py` → [[15-features/system/agent-core.md|Agent Core]]

