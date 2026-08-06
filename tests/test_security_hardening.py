"""Tests for v1.2 security hardening: secret redaction and API-key validation."""
from src.guardrails import _is_secret_key, _redact_sensitive
from src.main import mcp_api_key_error


class TestSecretRedaction:
    def test_catches_provider_specific_secret_fields(self):
        # The exact-match list used to miss these.
        for field in ("radius_secret", "ldap_bindpw", "ipsecpsk", "authorizedkeys",
                      "webrootftppassword", "cpanel_apitoken", "dnsexit_auth_pass",
                      "do_pw", "password", "pre_shared_key", "presharedkey", "prv"):
            assert _is_secret_key(field), field

    def test_does_not_over_redact_public_fields(self):
        for field in ("keylen", "keytype", "publickey", "certref", "name", "descr"):
            assert not _is_secret_key(field), field

    def test_redacts_nested_error_body(self):
        body = {
            "message": "validation failed",
            "data": {"radius_secret": "hunter2", "ldap_bindpw": "s3cr3t", "port": "636"},
        }
        red = _redact_sensitive(body)
        assert red["data"]["radius_secret"] == "***REDACTED***"
        assert red["data"]["ldap_bindpw"] == "***REDACTED***"
        assert red["data"]["port"] == "636"  # non-secret preserved


class TestApiKeyValidation:
    def test_unset_key_rejected(self):
        assert mcp_api_key_error(None) is not None
        assert mcp_api_key_error("   ") is not None

    def test_placeholder_rejected(self):
        for k in ("CHANGE-ME-generate-a-secure-token", "changeme", "change-me", "secret", "token"):
            assert mcp_api_key_error(k) is not None, k

    def test_short_key_rejected(self):
        assert mcp_api_key_error("abc123") is not None

    def test_strong_key_accepted(self):
        assert mcp_api_key_error("g7Qx2mVr8ThLpZ4wNc0aBdEf") is None

    def test_multi_key_all_must_be_valid(self):
        assert mcp_api_key_error("g7Qx2mVr8ThLpZ4wNc0a,CHANGE-ME-token") is not None
        assert mcp_api_key_error("g7Qx2mVr8ThLpZ4wNc0a,h8Ry3nWs9UiMqA5xOd1b") is None
