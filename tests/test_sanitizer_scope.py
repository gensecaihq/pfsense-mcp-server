"""The input sanitizer is scoped to threats meaningful for stored config data
(path traversal, stored XSS). Shell-injection rules were removed because tool
values are sent as JSON, not into a shell, and they false-positived on
legitimate values like multi-container LDAP DNs."""
import pytest

from src.guardrails import sanitize_input, sanitize_parameters


@pytest.mark.parametrize("value", [
    "CN=Users;DC=example,DC=com",          # multi-container LDAP DN
    "OU=eng;OU=corp;DC=example,DC=com",
    "desc: allow a | b routing",           # pipe in a description
    "push route 10.0.0.0; push dhcp-option",  # OpenVPN custom option style
    "https://host/path",                   # URL
])
def test_legitimate_values_are_not_rejected(value):
    assert sanitize_input(value, "field") is None


@pytest.mark.parametrize("value", [
    "../../etc/passwd",
    "config/../../secret",
    "<script>alert(1)</script>",
    "<SCRIPT src=x>",
])
def test_real_threats_still_rejected(value):
    assert sanitize_input(value, "field") is not None


def test_nested_and_list_params_scan_recursively():
    assert sanitize_parameters({"a": {"b": "../etc"}}) is not None
    assert sanitize_parameters({"a": ["ok", "<script>"]}) is not None
    assert sanitize_parameters({"a": {"b": "CN=x;DC=y"}}) is None
