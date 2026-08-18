"""Tests for tool-call middlewares (Phase G.10, Plan G v5)."""

from __future__ import annotations

import pytest

from eaccode import middlewares as mw


@pytest.fixture(autouse=True)
def _reset():
    mw.clear()
    yield
    mw.clear()


class TestPreRequest:
    def test_no_middlewares_returns_none(self) -> None:
        assert mw.run_pre_request("foo", {"x": 1}) is None

    def test_rewrite_args(self) -> None:
        def rewrite(name, args):
            if name == "write_file":
                args = dict(args)
                args["content"] = "[redacted]"
                return args
            return None

        mw.register_pre_request(rewrite)
        out = mw.run_pre_request("write_file", {"path": "x", "content": "secret"})
        assert out == {"path": "x", "content": "[redacted]"}

    def test_returns_first_non_none(self) -> None:
        def first(name, args):
            return {"a": 1}

        def second(name, args):
            return {"b": 2}

        mw.register_pre_request(first)
        mw.register_pre_request(second)
        assert mw.run_pre_request("x", {}) == {"a": 1}

    def test_middleware_exception_continues(self) -> None:
        def bad(name, args):
            raise RuntimeError("boom")

        def good(name, args):
            return {"recovered": True}

        mw.register_pre_request(bad)
        mw.register_pre_request(good)
        assert mw.run_pre_request("x", {}) == {"recovered": True}

    def test_unregister(self) -> None:
        def fn(name, args):
            return {"x": 1}

        mw.register_pre_request(fn)
        assert mw.run_pre_request("x", {}) == {"x": 1}
        mw.unregister(fn)
        assert mw.run_pre_request("x", {}) is None


class TestPreExecution:
    def test_no_middlewares_returns_none(self) -> None:
        assert mw.run_pre_execution("foo", {}) is None

    def test_short_circuit(self) -> None:
        def block(name, args):
            if "dangerous" in args.get("path", ""):
                return f"Error: blocked by middleware (path={args.get('path')!r})"
            return None

        mw.register_pre_execution(block)
        out = mw.run_pre_execution("write_file", {"path": "dangerous.txt"})
        assert out is not None
        assert "blocked" in out

    def test_passes_through(self) -> None:
        def block(name, args):
            return None

        mw.register_pre_execution(block)
        assert mw.run_pre_execution("write_file", {"path": "ok.txt"}) is None

    def test_middleware_exception_continues(self) -> None:
        def bad(name, args):
            raise RuntimeError("boom")

        def good(name, args):
            return "good-result"

        mw.register_pre_execution(bad)
        mw.register_pre_execution(good)
        assert mw.run_pre_execution("x", {}) == "good-result"


class TestClear:
    def test_clear_removes_all(self) -> None:
        mw.register_pre_request(lambda n, a: None)
        mw.register_pre_execution(lambda n, a: None)
        assert len(mw._REGISTRY.pre_request) == 1
        assert len(mw._REGISTRY.pre_execution) == 1
        mw.clear()
        assert len(mw._REGISTRY.pre_request) == 0
        assert len(mw._REGISTRY.pre_execution) == 0
