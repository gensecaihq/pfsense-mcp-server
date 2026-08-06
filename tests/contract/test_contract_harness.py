"""Prove the contract harness itself works: it accepts valid payloads and
catches the precise wire mistakes the audit found. If this file breaks, the
contract was regenerated incorrectly or the helper regressed.
"""
from tests.contract.schema import (
    CONTRACT_VERSION,
    check_payload,
    contract_for,
    endpoint_key,
    load_contract,
    missing_required,
)

OVPN_SERVER = "/vpn/openvpn/server"


def test_contract_loads_and_is_pinned():
    contract = load_contract()
    assert len(contract) > 100  # 233 endpoints in v2.9.0
    assert CONTRACT_VERSION == "v2.9.0"
    # The OpenVPN server model is present and rich.
    spec = contract_for("POST", OVPN_SERVER)
    assert "caref" in spec["properties"]
    assert spec["properties"]["data_ciphers"]["type"] == "array"


def test_endpoint_key_prefixes_api_v2():
    assert endpoint_key("post", "/vpn/openvpn/server") == "POST /api/v2/vpn/openvpn/server"
    assert endpoint_key("PATCH", "/api/v2/firewall/rule") == "PATCH /api/v2/firewall/rule"


def test_valid_payload_passes():
    payload = {
        "caref": "abc", "certref": "def", "dh_length": "2048",
        "data_ciphers": ["AES-256-GCM"], "data_ciphers_fallback": "AES-256-CBC",
        "description": "vpn", "disable": False, "local_port": "1194",
        "mode": "server_tls",
    }
    assert check_payload("POST", OVPN_SERVER, payload) == []


def test_unknown_field_is_caught():
    # `crypto`, `ca`, `cert`, `disabled`, `descr`, `compression` are NOT fields.
    for bad in ("crypto", "ca", "cert", "disabled", "descr", "compression"):
        violations = check_payload("POST", OVPN_SERVER, {bad: "x"})
        assert any("unknown field" in v and bad in v for v in violations), bad


def test_wrong_scalar_type_is_caught():
    # dh_length and local_port are strings upstream; sending int must fail.
    violations = check_payload("POST", OVPN_SERVER, {"dh_length": 2048, "local_port": 1194})
    assert any("dh_length" in v and "integer" in v for v in violations)
    assert any("local_port" in v and "integer" in v for v in violations)


def test_enum_membership_is_caught():
    # `mode` no longer allows p2p_shared_key upstream.
    violations = check_payload("POST", OVPN_SERVER, {"mode": "p2p_shared_key"})
    assert any("mode" in v and "choices" in v for v in violations)


def test_array_field_rejects_scalar():
    # data_ciphers is an array; a bare string element list is fine, a scalar isn't.
    violations = check_payload("POST", OVPN_SERVER, {"data_ciphers": "AES-256-GCM"})
    assert any("data_ciphers" in v for v in violations)


def test_missing_required_create_fields_detected():
    missing = missing_required("POST", OVPN_SERVER, {"description": "vpn"})
    assert "caref" in missing and "certref" in missing and "data_ciphers" in missing


def test_unknown_endpoint_raises():
    try:
        contract_for("POST", "/does/not/exist")
    except AssertionError as e:
        assert "No contract entry" in str(e)
    else:
        raise AssertionError("expected AssertionError for unknown endpoint")
