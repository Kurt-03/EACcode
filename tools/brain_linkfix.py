"""Rewrite every wikilink in the brain to root-path + alias form, then audit.

Convention: [[path/from/vault/root|Alias]] — never bare names, never ../ paths.
In markdown tables the pipe is escaped as \\| and must be preserved.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Projekte\EACcode V3\brain")

ALIAS: dict[str, str] = {
    "README.md": "Vault-Handbuch",
    "INDEX.md": "Index",
    "15-features/README.md": "Feature-Register",
    "10-projects/README.md": "Dashboard",
    "10-projects/phase-b.md": "Phase B",
    "30-research/README.md": "Research",
    "50-archive/phase-a.md": "Phase A",
    "wiki/README.md": "Wiki",
    "agents/README.md": "agents",
    "20-areas/architecture.md": "Architektur",
    "20-areas/vision.md": "Vision",
    "20-areas/tooling.md": "Tooling",
    "20-areas/testing.md": "Testing",
    "adr/0001-config-yaml-design.md": "ADR 0001",
    "adr/0002-phase-a-architecture.md": "ADR 0002",
    "15-features/system/config.md": "config.yaml",
    "15-features/system/secrets.md": "Secrets",
    "15-features/system/model-router.md": "Model Router",
    "15-features/system/agent-core.md": "Agent Core",
    "15-features/system/memory.md": "Memory",
    "15-features/system/repl.md": "REPL",
    "15-features/system/one-shot.md": "One-Shot",
    "15-features/system/tui.md": "TUI",
    "15-features/system/permission-gate.md": "Permission-Gate",
    "15-features/providers/openrouter.md": "OpenRouter",
    "15-features/providers/ollama.md": "Ollama",
}
for tool in [
    "read-file", "write-file", "list-files", "search-files", "run-command",
    "http-get", "web-search", "current-time", "system-info",
]:
    ALIAS[f"15-features/tools/{tool}.md"] = f"Tool: {tool.replace('-', '_')}"

LINK_RE = re.compile(r"\[\[([^\]\\|]+?)(\\?\|([^\]]*))?\]\]")


def main() -> int:
    files = {p.relative_to(ROOT).as_posix(): p for p in ROOT.rglob("*.md")}
    names: dict[str, list[str]] = {}
    for rel in files:
        names.setdefault(Path(rel).stem.lower(), []).append(rel)

    def resolve(target: str, source_rel: str) -> str:
        t = target.strip()
        candidates: list[str] = []
        if "/" in t or t.startswith("."):
            base = (files[source_rel].parent / t).resolve()
            candidates.append(base.as_posix())
        candidates.append((ROOT / t).as_posix())
        # author mistake: "../x" written from the wrong depth -> try as root path
        if t.startswith("."):
            candidates.append((ROOT / t.replace("../", "").strip("/")).as_posix())
        for cand in candidates:
            for suffix in ("", ".md"):
                try:
                    rel = Path(cand + suffix).relative_to(ROOT).as_posix()
                except ValueError:
                    continue
                if rel in files:
                    return rel
        hits = names.get(Path(t).stem.lower(), [])
        if len(hits) == 1:
            return hits[0]
        raise ValueError(f"UNRESOLVED: {t!r} from {source_rel} (hits={hits})")

    changed = 0
    for rel, path in sorted(files.items()):
        text = path.read_text(encoding="utf-8")

        def repl(m: re.Match[str]) -> str:
            nonlocal changed
            target, sep, alias = m.group(1), m.group(2), m.group(3)
            norm = resolve(target, rel)
            new_alias = ALIAS.get(norm) or Path(norm).stem
            escaped = sep is not None and sep.startswith("\\")
            bar = "\\|" if escaped else "|"
            if norm == target and (alias or "") == new_alias:
                return m.group(0)
            changed += 1
            return f"[[{norm}{bar}{new_alias}]]"

        new_text = LINK_RE.sub(repl, text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")

    print(f"{changed} links rewritten")

    # strict re-audit: every target must exist exactly as a root path
    problems = 0
    for rel, path in sorted(files.items()):
        text = path.read_text(encoding="utf-8")
        for m in LINK_RE.finditer(text):
            target = m.group(1).strip()
            if target not in files:
                problems += 1
                print(f"BROKEN: {rel} -> {target!r}")
    print(f"AUDIT: {problems} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
