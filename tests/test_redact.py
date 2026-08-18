"""Tests for redact.py (Phase C.2)."""

from __future__ import annotations

from eaccode.redact import Redactor, redact


class TestBasicRedaction:
    def test_github_pat(self) -> None:
        r = Redactor()
        out = r.redact("token ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567")
        # format: first3 + *** + last2 (or "ghp_aBc***67")
        assert "ghp" in out  # first 3 chars visible
        assert "***" in out  # middle masked
        assert "aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567" not in out  # no leak

    def test_anthropic_key_partial(self) -> None:
        r = Redactor()
        out = r.redact("key=sk-ant-abcdef1234567890XYZXYZABCDEFGHIJ1234567890")
        # sk- prefixed keys are masked as [first3]***[last2]
        assert "sk-" in out  # at least prefix visible
        assert "abcdef1234567890" not in out

    def test_openai_key(self) -> None:
        r = Redactor()
        out = r.redact("using sk-projabcdefghij1234567890")
        assert "sk-***" in out or "sk-p***0" in out or "sk-p***" in out
        assert "abcdefghij1234567890" not in out

    def test_bearer_token(self) -> None:
        r = Redactor()
        out = r.redact("Authorization: Bearer abc123def456ghi789jkl012mno345pq")
        assert "Bearer ***" in out or "Bearer" in out
        assert "abc123def456ghi789jkl012mno345pq" not in out

    def test_pem_block(self) -> None:
        r = Redactor()
        pem = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF5PC68xDq7LBY...\n"
            "-----END RSA PRIVATE KEY-----\n"
        )
        out = r.redact(pem)
        assert "[REDACTED-pem-key]" in out
        assert "MIIEpAIBAAKCAQEA" not in out

    def test_aws_access_key(self) -> None:
        r = Redactor()
        out = r.redact("AKIAIOSFODNN7EXAMPLE")
        assert "AKI***" in out or "AKI***LE" in out
        assert "IOSFODNN7EXAMPLE" not in out

    def test_jwt(self) -> None:
        r = Redactor()
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        out = r.redact(jwt)
        assert "eyJ" in out
        assert "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" not in out

    def test_safe_text_unchanged(self) -> None:
        r = Redactor()
        assert r.redact("hello world") == "hello world"
        assert r.redact("ls -la /tmp") == "ls -la /tmp"
        assert r.redact("1234567890") == "1234567890"  # too short


class TestModule:
    def test_module_helper(self) -> None:
        out = redact("see ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567 here")
        assert "ghp" in out
        assert "***" in out
        assert "aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567" not in out
