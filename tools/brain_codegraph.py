"""Generate the Code-Graph section for every brain feature note.

Scans src/eaccode/*.py imports, maps modules to their feature notes and
writes a linked "## Code-Graph" section into every note (idempotent).
Also runs a reachability audit: every note must be linked from elsewhere.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Projekte\EACcode V3")
BRAIN = ROOT / "brain"
SRC = ROOT / "src" / "eaccode"

# module -> note path (relative to brain root)
MODULE_NOTES: dict[str, str] = {
    "cli.py": "15-features/system/repl.md",
    "repl.py": "15-features/system/repl.md",
    "commands.py": "15-features/commands/README.md",
    "config.py": "15-features/system/config.md",
    "router.py": "15-features/system/model-router.md",
    "agent.py": "15-features/system/agent-core.md",
    "skills.py": "15-features/system/skill-system.md",
    "learning.py": "15-features/system/learning-loop.md",
    "memory.py": "15-features/system/memory.md",
    "store.py": "15-features/system/session-store.md",
    "subagents.py": "15-features/system/subagents.md",
    "tools.py": "15-features/system/tools-layer.md",
    "tui.py": "15-features/system/tui.md",
    "permissions.py": "15-features/system/permissions.md",
    "cron.py": "15-features/system/cron-daemon.md",
    "mcp.py": "15-features/system/mcp-client.md",
    "repo.py": "15-features/system/repo-understanding.md",
    # entry points: version (0.0.1) and `python -m eaccode`
    "__init__.py": "15-features/system/repl.md",
    "__main__.py": "15-features/system/repl.md",
}

IMPORT_RE = re.compile(
    r"^\s*(?:from eaccode(?:\.(\w+))? import ([^\n]+)|import eaccode\.(\w+))",
    re.MULTILINE,
)

SECTION_HEAD = "## Code-Graph (generiert)"


def module_imports() -> dict[str, list[str]]:
    """module filename -> imported eaccode module filenames."""
    graph: dict[str, list[str]] = {}
    for path in sorted(SRC.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        deps: list[str] = []
        for match in IMPORT_RE.finditer(text):
            sub = match.group(1) or match.group(3)
            if sub:
                deps.append(f"{sub}.py")
            else:
                for name in re.findall(r"\b(\w+)", match.group(2)):
                    if (SRC / f"{name}.py").exists():
                        deps.append(f"{name}.py")
        graph[path.name] = sorted(set(deps))
    return graph


def note_alias(note: str) -> str:
    """Short alias for a note path (frontmatter name or filename)."""
    stem = Path(note).stem
    return stem.replace("-", " ").title() if stem != "README" else "Index"


def build_section(module: str, deps: list[str]) -> str:
    links = []
    for dep in deps:
        note = MODULE_NOTES.get(dep)
        if note:
            links.append(f"[[{note}|{note_alias(note)}]]")
    deps_text = " · ".join(links) if links else "—"
    return f"- `src/eaccode/{module}` → {deps_text}"


def notes_for_module(module: str) -> list[str]:
    """All notes that reference this module (reverse mapping)."""
    return [note for mod, note in MODULE_NOTES.items() if mod == module and note]


def process_notes(graph: dict[str, list[str]]) -> int:
    changed = 0
    for module, note in MODULE_NOTES.items():
        target = BRAIN / note
        if not target.exists():
            print(f"MISSING NOTE for {module}: {note}")
            continue
        text = target.read_text(encoding="utf-8")
        lines = ["## Code-Graph (generiert)", ""]
        lines.append(build_section(module, graph.get(module, [])))
        lines.append("")
        section = "\n".join(lines)
        # replace existing generated section, or insert before Verknüpft
        if SECTION_HEAD in text:
            head_idx = text.index(SECTION_HEAD)
            tail = text[head_idx:]
            next_head = tail.find("\n## ")
            text = text[:head_idx] + (tail[next_head + 1 :] if next_head > 0 else "")
        new_text = text.rstrip() + "\n\n" + section + "\n"
        if new_text != text:
            target.write_text(new_text, encoding="utf-8")
            changed += 1
    return changed


def audit_reachability() -> None:
    """Every .md note must be linked from at least one other note."""
    notes = {p.relative_to(BRAIN).as_posix(): p for p in BRAIN.rglob("*.md")}
    linked: set[str] = set()
    for rel, path in notes.items():
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\[\[([^\]\\|]+)", text):
            target = m.group(1).strip() + (".md" if not m.group(1).endswith(".md") else "")
            if target in notes and target != rel:
                linked.add(target)
    unlinked = [rel for rel in notes if rel not in linked]
    print(f"reachability: {len(notes) - len(unlinked)}/{len(notes)} notes linked")
    for rel in sorted(unlinked):
        print(f"  UNLINKED: {rel}")


def main() -> int:
    graph = module_imports()
    changed = process_notes(graph)
    print(f"{changed} notes updated with Code-Graph")
    # every src module must be mapped to a note
    unmapped = sorted(set(SRC.glob("*.py")) - {path for path in _mapped_paths()})
    if unmapped:
        print("UNMAPPED SRC MODULES (no note):")
        for path in unmapped:
            print(f"  {path.name}")
    audit_reachability()
    return 0


def _mapped_paths() -> list[Path]:
    return [SRC / name for name in MODULE_NOTES]


if __name__ == "__main__":
    sys.exit(main())
