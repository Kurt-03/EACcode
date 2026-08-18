"""Permission pipeline trace — temporarily committed for the audit.

Not part of normal test suite. Run with:
  py -m pytest tests/test_pipeline_trace.py -v -s
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Ensure we import the source tree, not the installed package
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from eaccode import config as cfg  # noqa: E402
from eaccode.permissions import PermissionManager  # noqa: E402


# ----------------------------------------------------------------------
# Step 1: Build a fake (manager, ask_handler, smart_reviewer) and walk
# the check() pipeline with a fake LLM "intent" of read_file/list_files.
# ----------------------------------------------------------------------


def _conf(tmp_path: Path) -> dict[str, Any]:
    """Build a minimal smart-mode config."""
    cfg.config_dir = lambda: tmp_path   # type: ignore[assignment]
    cfg.data_dir = lambda: tmp_path     # type: ignore[assignment]
    cfg.ensure_config()
    return {"permissions": {"mode": "smart", "allow": [], "deny": []}}


def trace_read_file(tmp_path: Path) -> None:
    """A. Smart-Mode Read-Only-Pfad: list_files / read_file."""
    print("\n=== A. Smart-Mode Read-Only-Pfad: list_files ===")
    conf = _conf(tmp_path)
    ask_calls: list[str] = []
    smart_calls: list[str] = []

    def ask_handler(name: str, args: dict[str, Any]) -> bool:
        ask_calls.append(name)
        return True

    def smart_reviewer(cmd: str, desc: str) -> str:
        smart_calls.append(desc)
        return "approve"

    mgr = PermissionManager(conf, ask_handler=ask_handler,
                            smart_reviewer=smart_reviewer)
    d = mgr.check("list_files", {"path": "."})
    print(f"  list_files -> allow={d.allow} reason={d.reason!r}")
    print(f"  ask_calls={ask_calls} smart_calls={smart_calls}")
    assert d.allow, "list_files should auto-approve in smart mode"
    assert ask_calls == [], "list_files should NOT prompt the user"
    assert smart_calls == [], "list_files should NOT trigger aux LLM"

    print("\n=== A. Smart-Mode Read-Only-Pfad: read_file (regular path) ===")
    ask_calls.clear()
    smart_calls.clear()
    d = mgr.check("read_file", {"path": "src/eaccode/agent.py"})
    print(f"  read_file -> allow={d.allow} reason={d.reason!r}")
    print(f"  ask_calls={ask_calls} smart_calls={smart_calls}")
    assert d.allow
    assert ask_calls == []
    assert smart_calls == []


def trace_read_file_env(tmp_path: Path) -> None:
    """C. Sensitive-Path Bug: read_file on /repo/.env."""
    print("\n=== C. Sensitive-Path: read_file /repo/.env ===")
    conf = _conf(tmp_path)
    ask_calls: list[str] = []
    smart_calls: list[str] = []

    def ask_handler(name: str, args: dict[str, Any]) -> bool:
        ask_calls.append(name)
        return True

    def smart_reviewer(cmd: str, desc: str) -> str:
        smart_calls.append(desc)
        return "approve"

    mgr = PermissionManager(conf, ask_handler=ask_handler,
                            smart_reviewer=smart_reviewer)
    d = mgr.check("read_file", {"path": "/repo/.env"})
    print(f"  read_file /repo/.env -> allow={d.allow} reason={d.reason!r}")
    print(f"  ask_calls={ask_calls} smart_calls={smart_calls}")
    # The bug: read_file is NOT in _mutating_tools, so the file_safety
    # 5a skip happens, but the generic 5b _is_sensitive_path HIT
    # triggers _ask_user anyway.

    print("\n=== C. Sensitive-Path: read_file C:/Users/kurtj/.env ===")
    ask_calls.clear()
    smart_calls.clear()
    d = mgr.check("read_file", {"path": "C:/Users/kurtj/.env"})
    print(f"  read_file C:/Users/kurtj/.env -> allow={d.allow} reason={d.reason!r}")
    print(f"  ask_calls={ask_calls} smart_calls={smart_calls}")


def trace_write_file(tmp_path: Path) -> None:
    """E. Test the whole pipeline: write_file on a normal path."""
    print("\n=== E. write_file on a normal path (smart mode) ===")
    conf = _conf(tmp_path)
    ask_calls: list[str] = []
    smart_calls: list[str] = []

    def ask_handler(name: str, args: dict[str, Any]) -> bool:
        ask_calls.append(name)
        return True

    def smart_reviewer(cmd: str, desc: str) -> str:
        smart_calls.append(desc)
        return "approve"

    mgr = PermissionManager(conf, ask_handler=ask_handler,
                            smart_reviewer=smart_reviewer)
    d = mgr.check("write_file", {"path": "hello.txt", "content": "x"})
    print(f"  write_file hello.txt -> allow={d.allow} reason={d.reason!r}")
    print(f"  ask_calls={ask_calls} smart_calls={smart_calls}")


def trace_run_command(tmp_path: Path) -> None:
    """B. Aux-LLM Coverage: run_command."""
    print("\n=== B. Aux-LLM Coverage: run_command ===")
    conf = _conf(tmp_path)
    ask_calls: list[str] = []
    smart_calls: list[str] = []

    def ask_handler(name: str, args: dict[str, Any]) -> bool:
        ask_calls.append(name)
        return True

    def smart_reviewer(cmd: str, desc: str) -> str:
        smart_calls.append(desc)
        return "approve"

    mgr = PermissionManager(conf, ask_handler=ask_handler,
                            smart_reviewer=smart_reviewer)

    # Safe command
    d = mgr.check("run_command", {"command": "ls -la"})
    print(f"  run_command 'ls -la' -> allow={d.allow} reason={d.reason!r}")

    # Dangerous pattern
    smart_calls.clear()
    d = mgr.check("run_command", {"command": "chmod 777 /tmp"})
    print(f"  run_command 'chmod 777 /tmp' -> allow={d.allow} reason={d.reason!r}")
    print(f"  smart_calls={smart_calls}  # Expected: should always invoke "
          "aux LLM here")

    # Dangerous pattern not on list (e.g. cwd listing)
    smart_calls.clear()
    d = mgr.check("run_command", {"command": "find . -name '*.py' -delete"})
    print(f"  run_command find-delete -> allow={d.allow} reason={d.reason!r}")
    print(f"  smart_calls={smart_calls}")


def trace_mutating_tool(tmp_path: Path) -> None:
    """D. What about a mutating tool that is NOT run_command?
    e.g. write_file, patch_file, git_commit, browser_click."""
    print("\n=== D. Mutating non-run_command tools ===")
    conf = _conf(tmp_path)
    ask_calls: list[str] = []
    smart_calls: list[str] = []

    def ask_handler(name: str, args: dict[str, Any]) -> bool:
        ask_calls.append(name)
        return True

    def smart_reviewer(cmd: str, desc: str) -> str:
        smart_calls.append(desc)
        return "approve"

    mgr = PermissionManager(conf, ask_handler=ask_handler,
                            smart_reviewer=smart_reviewer)

    for tool, args in [
        ("write_file", {"path": "x", "content": "y"}),
        ("patch_file", {"path": "x", "old": "1", "new": "2"}),
        ("git_commit", {"message": "fix"}),
        ("browser_click", {"ref": "r1"}),
        ("browser_navigate", {"url": "https://example.com"}),
    ]:
        smart_calls.clear()
        ask_calls.clear()
        d = mgr.check(tool, args)
        print(f"  {tool} -> allow={d.allow} reason={d.reason!r}")
        print(f"    ask_calls={ask_calls} smart_calls={smart_calls}")


def main() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        trace_read_file(tmp_path)
        trace_read_file_env(tmp_path)
        trace_write_file(tmp_path)
        trace_run_command(tmp_path)
        trace_mutating_tool(tmp_path)


if __name__ == "__main__":
    main()
