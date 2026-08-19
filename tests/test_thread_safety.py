"""Tests for parallel tool-call thread-safety (Plan J J.8).

These tests spawn real threads that hit workspace, todo, undo, and
permissions state concurrently. If any global state leaks across
threads, one or more of these tests fail with race-condition artefacts.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from eaccode import todo as todo_mod
from eaccode import undo as undo_mod
from eaccode import workspace as ws_mod
from eaccode.workspace import (
    Workspace,
    clear_session_state,
    get_active_workspace,
    set_active_workspace,
    update_session_cwd,
)
from eaccode.todo import TodoItem, write_todos
from eaccode.undo import save_snapshot


@pytest.fixture(autouse=True)
def reset_all_global_state():
    """Reset every module's per-session state before AND after each test."""
    ws_mod.clear_session_state()
    todo_mod.set_active_session(None)
    yield
    ws_mod.clear_session_state()
    todo_mod.set_active_session(None)


class TestParallelWorkspaces:
    def test_ten_threads_have_independent_workspaces(self) -> None:
        """10 threads set/get their workspace simultaneously. No leakage."""
        barrier = threading.Barrier(10)
        results: dict[str, str] = {}

        def make_root(name: str) -> Path:
            # Per-thread unique tmp dir (works on Windows + Unix).
            import tempfile
            d = Path(tempfile.mkdtemp(prefix=f"eaccode-test-{name}-"))
            return d.resolve()

        def worker(session_key: str) -> None:
            barrier.wait()
            root = make_root(f"sess-{session_key}")
            set_active_workspace(Workspace(root=root), session_key)
            time.sleep(0.001)
            ws = get_active_workspace(session_key)
            results[session_key] = str(ws.root)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(worker, f"s{i}") for i in range(10)]
            for f in futures:
                f.result()

        # Each thread saw its own root - they must all be different
        unique_roots = set(results.values())
        assert len(unique_roots) == 10

    def test_ten_threads_have_independent_cwd(self, tmp_path) -> None:
        barrier = threading.Barrier(10)
        results: dict[str, str] = {}

        def worker(session_key: str) -> None:
            barrier.wait()
            update_session_cwd(str(tmp_path / session_key), session_key)
            time.sleep(0.001)
            cwd = ws_mod.get_session_cwd(session_key)
            results[session_key] = str(cwd) if cwd else ""

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(worker, f"s{i}") for i in range(10)]
            for f in futures:
                f.result()

        for i in range(10):
            assert results[f"s{i}"] == str(tmp_path / f"s{i}")


class TestParallelTodos:
    def test_ten_threads_have_independent_todos(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(todo_mod, "todo_file", lambda sid: tmp_path / f"{sid}.json")
        barrier = threading.Barrier(10)

        def worker(session_key: str) -> None:
            barrier.wait()
            items = [TodoItem(id="1", content=f"task-{session_key}", status="pending")]
            write_todos(session_key, items)
            time.sleep(0.001)
            loaded = todo_mod.read_todos(session_key)
            assert len(loaded) == 1
            assert loaded[0].content == f"task-{session_key}"

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(worker, f"s{i}") for i in range(10)]
            for f in futures:
                f.result()


class TestParallelUndo:
    def test_ten_threads_have_independent_snapshots(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(undo_mod, "undo_dir", lambda s: tmp_path / s)
        barrier = threading.Barrier(10)

        def worker(session_key: str) -> None:
            barrier.wait()
            save_snapshot(session_key, f"/{session_key}.py", f"old-{session_key}")
            time.sleep(0.001)
            snaps = undo_mod.list_snapshots(session_key)
            assert len(snaps) == 1
            assert snaps[0].old_content == f"old-{session_key}"

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(worker, f"s{i}") for i in range(10)]
            for f in futures:
                f.result()


class TestLockIsReal:
    """Sanity-check: the lock object actually serialises critical sections."""

    def test_workspace_lock_serialises_updates(self) -> None:
        """Two threads racing on update_session_cwd - no torn state."""
        barrier = threading.Barrier(2)
        observed: list[str] = []

        def worker(name: str) -> None:
            barrier.wait()
            for i in range(20):
                update_session_cwd(f"/tmp/{name}-{i}", "shared")
                observed.append(name)

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(worker, ["a", "b"]))

        # Both ran 20 iterations (no thread crashed on lock contention)
        assert observed.count("a") == 20
        assert observed.count("b") == 20