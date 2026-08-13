"""Tests for the skill system (Phase B1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eaccode import config as cfg
from eaccode import skills


@pytest.fixture
def tmp_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(cfg, "data_dir", lambda: tmp_path)
    return tmp_path / "skills"


class TestParse:
    def test_parse_full_skill(self) -> None:
        skill = skills.parse_skill(
            "---\n"
            "name: echo-test\n"
            "description: echoes back\n"
            "trigger: echo\n"
            "---\n"
            "# Echo\n"
            "Always reply with the text.\n"
        )
        assert skill.name == "echo-test"
        assert skill.description == "echoes back"
        assert skill.trigger == "echo"
        assert "Always reply" in skill.body

    def test_parse_without_frontmatter_raises(self) -> None:
        with pytest.raises(skills.SkillError, match="frontmatter"):
            skills.parse_skill("no frontmatter here")

    def test_parse_bad_yaml_raises(self) -> None:
        with pytest.raises(skills.SkillError):
            skills.parse_skill("---\nname: [unclosed\n---\nbody")

    def test_render_roundtrip(self) -> None:
        skill = skills.parse_skill(
            "---\nname: a\ndescription: d\ntrigger: t\n---\n# Body\ncontent\n"
        )
        reparsed = skills.parse_skill(skills.render_skill(skill))
        assert reparsed.name == "a"
        assert reparsed.trigger == "t"
        assert reparsed.body == "# Body\ncontent"


class TestRegistry:
    def test_list_empty(self, tmp_skills: Path) -> None:
        assert skills.list_skills() == []

    def test_create_and_list(self, tmp_skills: Path) -> None:
        skills.create_skill("web-help", "web tips", "webseite")
        skills.create_skill("zeit", "time info", "uhrzeit")
        names = [s.name for s in skills.list_skills()]
        assert names == ["web-help", "zeit"]  # sorted

    def test_create_duplicate_raises(self, tmp_skills: Path) -> None:
        skills.create_skill("x", "d", "t")
        with pytest.raises(skills.SkillError, match="already exists"):
            skills.create_skill("x", "d", "t2")

    def test_create_duplicate_trigger_raises(self, tmp_skills: Path) -> None:
        skills.create_skill("a", "d", "trigger1")
        with pytest.raises(skills.SkillError, match="already used"):
            skills.create_skill("b", "d", "trigger1")

    def test_force_overwrites(self, tmp_skills: Path) -> None:
        skills.create_skill("x", "alt", "t")
        skills.create_skill("x", "neu", "t", force=True)
        assert skills.list_skills()[0].description == "neu"

    def test_invalid_name_raises(self, tmp_skills: Path) -> None:
        with pytest.raises(skills.SkillError, match="invalid skill name"):
            skills.create_skill("Bad Name!", "d", "t")

    def test_update_body_keeps_meta(self, tmp_skills: Path) -> None:
        skills.create_skill("x", "d", "t", body="alt")
        updated = skills.update_skill("x", "NEUER INHALT")
        assert updated.body == "NEUER INHALT"
        assert updated.trigger == "t"
        assert skills.list_skills()[0].description == "d"

    def test_update_missing_raises(self, tmp_skills: Path) -> None:
        with pytest.raises(skills.SkillError, match="does not exist"):
            skills.update_skill("ghost", "x")

    def test_remove(self, tmp_skills: Path) -> None:
        skills.create_skill("x", "d", "t")
        assert "removed" in skills.remove_skill("x")
        assert skills.list_skills() == []

    def test_remove_missing_raises(self, tmp_skills: Path) -> None:
        with pytest.raises(skills.SkillError, match="does not exist"):
            skills.remove_skill("ghost")

    def test_broken_skill_skipped(self, tmp_skills: Path) -> None:
        skills.create_skill("ok", "d", "t")
        (tmp_skills / "kaputt").mkdir()
        (tmp_skills / "kaputt" / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
        assert [s.name for s in skills.list_skills()] == ["ok"]


class TestMatching:
    def test_match_case_insensitive_substring(self, tmp_skills: Path) -> None:
        skills.create_skill("zeit", "time", "uhrzeit")
        hits = skills.match_skills("Wie spät ist es? Zeig mir die UHRZEIT an")
        assert [s.name for s in hits] == ["zeit"]

    def test_match_limit(self, tmp_skills: Path) -> None:
        for index, trigger in enumerate(["h", "a", "l", "o", "u"]):
            skills.create_skill(f"s{index}", "d", trigger)
        assert len(skills.match_skills("hallo du")) == skills.MAX_INJECT

    def test_no_match(self, tmp_skills: Path) -> None:
        skills.create_skill("zeit", "time", "uhrzeit")
        assert skills.match_skills("irgendwas anderes") == []

    def test_injection_block_empty_without_hits(self, tmp_skills: Path) -> None:
        assert skills.injection_block("nichts") == ""

    def test_injection_block_contains_bodies(self, tmp_skills: Path) -> None:
        skills.create_skill("zeit", "time info", "uhrzeit", body="Nutze current_time.")
        block = skills.injection_block("Wie spät ist es? UHRZEIT bitte")
        assert "## Relevant skills" in block
        assert "zeit" in block
        assert "Nutze current_time." in block

    def test_find_by_trigger(self, tmp_skills: Path) -> None:
        skills.create_skill("zeit", "time", "uhrzeit")
        assert skills.find_by_trigger("uhrzeit").name == "zeit"
        assert skills.find_by_trigger("unbekannt") is None
