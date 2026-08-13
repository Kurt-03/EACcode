"""Tests for subagents (Phase B5)."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from eaccode import config as cfg
from eaccode.agent import Tool
from eaccode.subagents import SubagentPool, make_subagent_tool


class FakeSubAgent:
    """Agent double for pool tests: answers instantly or after a delay."""

    def __init__(self, reply: str = "sub-antwort", delay: float = 0.0) -> None:
        self.reply = reply
        self.delay = delay
        self.system_prompt = "subagent"

    def run(self, messages: list[dict[str, str]], **kwargs: Any) -> list[dict[str, Any]]:
        if self.delay:
            time.sleep(self.delay)
        return messages + [{"role": "assistant", "content": self.reply}]

    def last_text(self, history: list[dict[str, Any]]) -> str:
        return self.reply


def _factory(reply: str = "sub-antwort", delay: float = 0.0):
    return lambda: FakeSubAgent(reply=reply, delay=delay)


def test_pool_runs_subagent(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    pool = SubagentPool(agent_factory=_factory("hallo aus dem subagent"))
    out = pool.run("Aufgabe", [])
    assert out == "hallo aus dem subagent"


def test_pool_context_passed(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    seen: dict[str, Any] = {}

    class RecordingAgent(FakeSubAgent):
        def run(self, messages: list[dict[str, str]], **kwargs: Any) -> list[dict[str, Any]]:
            seen["messages"] = messages
            return super().run(messages, **kwargs)

    pool = SubagentPool(agent_factory=lambda: RecordingAgent())
    pool.run("Löse das Problem", [], context="Der Kontext: XYZ")
    roles = [m["role"] for m in seen["messages"]]
    assert roles == ["system", "user"]
    assert "Kontext" in seen["messages"][0]["content"]


def test_pool_error_propagates_as_string(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)

    class BoomAgent(FakeSubAgent):
        def run(self, messages: list[dict[str, str]], **kwargs: Any) -> list[dict[str, Any]]:
            raise RuntimeError("subagent kaputt")

    pool = SubagentPool(agent_factory=lambda: BoomAgent())
    out = pool.run("x", [])
    assert "kaputt" in out


def test_pool_timeout(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    pool = SubagentPool(agent_factory=_factory(delay=5.0))
    out = pool.run("x", [], timeout=0.3)
    assert "timed out" in out
    assert "cancelled" in out


def test_pool_concurrency_limit(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    pool = SubagentPool(agent_factory=_factory(delay=0.5), max_parallel=2)
    lock = threading.RLock()  # reentrant: track() locks again
    peak = [0]

    def track() -> None:
        with lock:
            peak[0] = max(peak[0], pool.active)

    started = threading.Event()
    results: list[str] = []

    def worker(index: int) -> None:
        started.wait()
        track()
        results.append(pool.run(f"task {index}", []))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    started.set()
    for t in threads:
        t.join()
    assert peak[0] <= 2
    assert len(results) == 4


def test_spawn_tool_unknown_tool(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    pool = SubagentPool(agent_factory=_factory())
    tool = make_subagent_tool(pool, {"read_file": Tool("read_file", "d", lambda: "")}, {})
    out = tool.func(task="x", tools=["ghost_tool"])
    assert "unknown tool" in out


def test_spawn_tool_reasoning_only_allowed(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    pool = SubagentPool(agent_factory=_factory("gedicht"))
    tool = make_subagent_tool(pool, {}, {})
    out = tool.func(task="Schreibe ein Gedicht", tools=[])
    assert out == "gedicht"


def test_spawn_tool_runs_with_selected_tools(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    used: dict[str, Any] = {}
    pool = SubagentPool(
        agent_factory=lambda: _ToolRecordingAgent(used),
    )
    echo = Tool("echo", "echo", lambda text: f"echo:{text}")
    tool = make_subagent_tool(pool, {"echo": echo}, {})
    out = tool.func(task="tu was", tools=["echo"])
    assert out == "sub-antwort"


class _ToolRecordingAgent(FakeSubAgent):
    def __init__(self, used: dict[str, Any]) -> None:
        super().__init__()
        self.used = used

    def run(self, messages: list[dict[str, str]], **kwargs: Any) -> list[dict[str, Any]]:
        self.used["kwargs"] = kwargs
        return super().run(messages, **kwargs)
