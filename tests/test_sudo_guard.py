"""Test sudo-stdin-guard (Phase 1, H7)."""

from __future__ import annotations

from eaccode.sudo_guard import is_sudo_stdin_guess


class TestMatches:
    def test_sudo_S(self) -> None:
        assert is_sudo_stdin_guess("sudo -S cat /etc/shadow")[0]

    def test_sudo_stdin(self) -> None:
        assert is_sudo_stdin_guess("sudo --stdin ls")[0]

    def test_sudo_A(self) -> None:
        assert is_sudo_stdin_guess("sudo -A ls")[0]

    def test_sudo_askpass(self) -> None:
        assert is_sudo_stdin_guess("sudo --askpass ls")[0]

    def test_echo_pipe_sudo_S(self) -> None:
        assert is_sudo_stdin_guess("echo 'passwd' | sudo -S cat /etc/shadow")[0]

    def test_password_var_pipe(self) -> None:
        assert is_sudo_stdin_guess("$PASSWORD | sudo -S cat /etc/shadow")[0]

    def test_sudo_rm(self) -> None:
        assert is_sudo_stdin_guess("echo x | sudo -S rm -rf /etc")[0]

    def test_safe_sudo(self) -> None:
        # sudo without flags is allowed (sensible usage like "sudo apt update")
        assert not is_sudo_stdin_guess("sudo apt update")[0]

    def test_safe_ls(self) -> None:
        assert not is_sudo_stdin_guess("ls -la")[0]

    def test_safe_sudo_cat(self) -> None:
        # sudo with file but no stdin-flag
        assert not is_sudo_stdin_guess("sudo cat /etc/hostname")[0]

    def test_empty_command(self) -> None:
        assert is_sudo_stdin_guess("") == (False, "")


class TestReturns:
    def test_returns_description(self) -> None:
        ok, desc = is_sudo_stdin_guess("sudo -S ls")
        assert ok
        assert "sudo" in desc.lower() or "password" in desc.lower()
