"""Tests for the learning loop (Phase B2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import config as cfg
from eaccode import learning, skills


@pytest.fixture
def tmp_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    return tmp_path / "skills"


class TestLearningTools:
    def test_tools_registered(self) -> None:
        names = {tool.name for tool in learning.make_learning_tools()}
        assert {"create_skill", "improve_skill", "list_skills"} <= names

    def test_create_tool_writes_skill(self, tmp_skills: Path) -> None:
        tool = next(t for t in learning.make_learning_tools() if t.name == "create_skill")
        out = tool.func(name="test-skill", description="d", trigger="testfall", body="Schritt 1")
        assert "created" in out
        assert skills.list_skills()[0].name == "test-skill"

    def test_create_duplicate_returns_error(self, tmp_skills: Path) -> None:
        tool = next(t for t in learning.make_learning_tools() if t.name == "create_skill")
        tool.func(name="x", description="d", trigger="t1")
        out = tool.func(name="x", description="d", trigger="t2")
        assert "already exists" in out

    def test_improve_tool_updates_body(self, tmp_skills: Path) -> None:
        skills.create_skill("x", "d", "t", body="alt")
        tool = next(t for t in learning.make_learning_tools() if t.name == "improve_skill")
        out = tool.func(name="x", body="besserer Inhalt")
        assert "updated" in out
        assert skills.list_skills()[0].body == "besserer Inhalt"

    def test_improve_missing_returns_error(self, tmp_skills: Path) -> None:
        tool = next(t for t in learning.make_learning_tools() if t.name == "improve_skill")
        assert "does not exist" in tool.func(name="ghost", body="x")

    def test_list_tool_shows_skills(self, tmp_skills: Path) -> None:
        skills.create_skill("zeit", "time", "uhrzeit")
        tool = next(t for t in learning.make_learning_tools() if t.name == "list_skills")
        out = tool.func()
        assert "zeit" in out
        assert "uhrzeit" in out

    def test_list_empty(self, tmp_skills: Path) -> None:
        tool = next(t for t in learning.make_learning_tools() if t.name == "list_skills")
        assert "no skills yet" in tool.func()

    def test_learning_prompt_mentions_review(self) -> None:
        assert "create_skill" in learning.LEARNING_PROMPT
        assert "improve_skill" in learning.LEARNING_PROMPT
