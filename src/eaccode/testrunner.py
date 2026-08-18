"""Test runner (Phase D3): pytest invocation with failure parsing.

The agent uses ``run_tests`` to execute a suite and gets a structured
report: pass/fail counts, exit code and parsed failure details. Coverage
is optional (pytest-cov when installed).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from eaccode.agent import Tool

FAILED_RE = re.compile(r"^FAILED ([^ \n]+)( - .*)?$", re.MULTILINE)
ERROR_RE = re.compile(r"^ERROR ([^ \n]+)( - .*)?$", re.MULTILINE)
SUMMARY_RE = re.compile(
    r"^(\d+) passed(?:, (\d+) (?:failed|error))?(?:, (\d+) skipped)?", re.MULTILINE
)


def _pytest_attempts(test_file: str | None, coverage: bool) -> list[list[str]]:
    """Candidate pytest invocations, most isolated first."""
    base = ["-q", "--tb=short", "--no-header"]
    if test_file:
        base.append(test_file)
    if coverage:
        base.extend(["--cov=", "--cov-report=term-missing"])
    attempts = [[sys.executable, "-m", "pytest", *base]]
    if shutil.which("uv"):
        attempts.append(["uv", "run", "pytest", *base])
    if shutil.which("pytest"):
        attempts.append(["pytest", *base])
    return attempts


def run_tests(
    path: str = ".",
    test_file: str | None = None,
    timeout: int = 600,
    coverage: bool = False,
) -> str:
    """Run pytest in a directory; returns a structured report.

    Falls back from the isolated interpreter to `uv run pytest` and a
    PATH `pytest` when the module is not installed (e.g. tool venvs).
    """
    base = Path(path).expanduser().resolve()
    if not base.exists():
        return f"Error: no such directory: {path}"
    last_output = "Error: no pytest found on any path"
    for attempt in _pytest_attempts(test_file, coverage):
        try:
            result = subprocess.run(
                attempt,
                cwd=str(base),
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            return f"Error: tests timed out after {timeout}s"
        except OSError as exc:
            last_output = f"Error: cannot run pytest: {exc}"
            continue
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0 and "No module named" in output:
            last_output = output  # try the next interpreter
            continue
        return format_report(output, result.returncode)
    return format_report(last_output, 1)


def parse_failures(output: str) -> list[str]:
    """Extract FAILED/ERROR test ids from pytest output."""
    failed = [match.group(1) for match in FAILED_RE.finditer(output)]
    errors = [match.group(1) for match in ERROR_RE.finditer(output)]
    return failed + errors


def format_report(output: str, exit_code: int) -> str:
    """Turn raw pytest output into a compact structured report."""
    failed = parse_failures(output)
    summary_match = SUMMARY_RE.search(output)
    if summary_match:
        passed = summary_match.group(1)
        problems = summary_match.group(2) or "0"
        skipped = summary_match.group(3) or "0"
        summary = f"passed {passed}, failed/errors {problems}, skipped {skipped}"
    else:
        summary = "no summary line found"
    status = "OK" if exit_code == 0 else "FAIL"
    lines = [f"tests: {status} (exit {exit_code})", summary]
    if failed:
        lines.append("failed tests:")
        lines.extend(f"  {name}" for name in failed[:20])
    if exit_code != 0 and len(output) < 4000:
        lines.append("output:")
        lines.extend(f"  {line}" for line in output.splitlines()[:40])
    return "\n".join(lines)


def _tool_run_tests(path: str = ".", test_file: str | None = None) -> str:
    return run_tests(path, test_file)


def make_test_tools() -> list[Tool]:
    """Agent tools for running tests (D3)."""
    return [
        Tool(
            "run_tests",
            "Run the pytest suite in a directory. Returns 'X passed, "
            "Y failed' plus the failing test ids and tail; 'Error: pytest "
            "not installed' when pytest is missing. POLICY: run after "
            "every code change; never declare work done while tests are "
            "red. never commit (git_commit) while tests are red.",
            _tool_run_tests,
            {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project root (default: cwd).",
                    },
                    "test_file": {
                        "type": "string",
                        "description": (
                            "Single test file to run (default: full "
                            "suite, e.g. 'tests/test_x.py')."
                        ),
                    },
                },
                "required": [],
            },
            mutates=False,
        ),
    ]
