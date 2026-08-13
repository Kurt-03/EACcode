---
date: 2026-08-13
status: active
area: testing
tags: [area/testing, type/area]
---

# Testing & Verifikation *(timeless)*

## Grundsätze

- **TDD:** Tests vor Code, RED→GREEN→REFACTOR; kein Commit bei roten Tests.
- **4 Stufen pro Step:** ① pytest grün → ② ruff clean → ③ Live-Check in der
  eaccode-Session → ④ Commit.
- **Test-Map:** die fortlaufende „wie wird was getestet"-Liste liegt im Repo
  (`docs/test-map.md`) — wird bei jedem Schritt ergänzt; ausführliche
  Anleitungen in `docs/manual-test.md`.
- **Live-Verifikation ist Pflicht:** Unit-Tests sind kein Beweis — jeder Step
  hat einen echten Kommando-Check (`docs/manual-test.md` im Repo)
- **Ein Feature pro Iteration:** bauen → verifizieren → committen → weiter
- **Fehler melden:** Kommando + echte Ausgabe + Erwartung vs. Ergebnis

## Test-Matrix (Stand Phase A)

- 150 Tests + 3 POSIX-Skips (laufen in CI auf Linux) — Stand 2026-08-13
- *(Pointer: aktueller Stand immer via `uv run pytest` im Repo)*

## CI (GitHub Actions)

- Matrix: ubuntu / windows / macos → `uv sync` + `ruff check` + `pytest`

## Bekannte Fallen

- Hermes-Desktop-Terminal maskiert gelegentlich `not`/`None` in der Anzeige
  als `***` → echte Ausgabe per Datei-Umleitung prüfen (`cmd > datei.txt`)
