"""Test command normalization + parser-limit (Phase 1, H4/H5/H6)."""

from __future__ import annotations

import sys

from eaccode.command_normalize import (
    COMMAND_PARSER_LIMIT,
    _command_parser_limit_exceeded,
    normalize_command_for_detection,
)


class TestNormalize:
    def test_strips_whitespace(self) -> None:
        assert normalize_command_for_detection("  rm   -rf  /  ") == (
            "rm -rf /"
        )

    def test_strips_outer_quotes(self) -> None:
        assert normalize_command_for_detection('"rm -rf /"') == "rm -rf /"
        assert normalize_command_for_detection("'rm -rf /'") == "rm -rf /"

    def test_empty(self) -> None:
        assert normalize_command_for_detection("") == ""

    def test_tilde_to_home(self) -> None:
        norm = normalize_command_for_detection("rm -rf ~")
        # ~ becomes Path.home()
        from pathlib import Path

        assert str(Path.home()) in norm

    def test_tilde_slash_to_home(self) -> None:
        norm = normalize_command_for_detection("rm -rf ~/foo")
        from pathlib import Path

        assert f"{Path.home()}/foo" in norm

    def test_dangerous_pattern_matches_after_normalize(self) -> None:
        """The whole point: normalize so pattern works on weird inputs."""
        import re

        pattern = re.compile(r"\brm\s+(-[rRfi]+\s+)*\.")
        messy = '   rm   -rf  . '
        assert pattern.search(normalize_command_for_detection(messy))


class TestParserLimit:
    def test_short_command_safe(self) -> None:
        assert not _command_parser_limit_exceeded("ls -la")

    def test_long_command_exceeds(self) -> None:
        # Construct a > max_len command
        long_cmd = "echo " + ("a " * (COMMAND_PARSER_LIMIT + 100))
        assert _command_parser_limit_exceeded(long_cmd)

    def test_too_many_subshells(self) -> None:
        # 6+ $() subshells in one command
        cmd = "echo $(a) $(b) $(c) $(d) $(e) $(f)"
        assert _command_parser_limit_exceeded(cmd)

    def test_shlex_unparseable(self) -> None:
        # Unbalanced quotes make shlex.parse fail
        assert _command_parser_limit_exceeded("echo 'unclosed")

    def test_too_many_tokens(self) -> None:
        # 200+ tokens
        cmd = " ".join(["arg"] * 250)
        assert _command_parser_limit_exceeded(cmd)

    def test_normal_command_within_limit(self) -> None:
        assert not _command_parser_limit_exceeded(
            "find . -name '*.py' -exec rm -i {} \\;"
        )
