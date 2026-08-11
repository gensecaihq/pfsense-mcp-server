"""Contract tests for the IPsec Phase 2 encryption wire fix.

The IPsecPhase2Encryption model has only `name`, `keylen`, and `parent_id`. The
pre-fix tool sent `encryption_algorithm_name`/`encryption_algorithm_keylen` plus
phase1-only fields (hash_algorithm/dhgroup/prf_algorithm), so create 400'd on
the missing required `name` and the extras were silently dropped.
"""
from src.tools.vpn_advanced import (
    create_ipsec_phase2_encryption,
    update_ipsec_phase2_encryption,
)
from tests.contract.schema import assert_payload_valid, capture_call


class TestPhase2Encryption:
    async def test_create_uses_name_and_keylen(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_ipsec_phase2_encryption(
            parent_id=1, encryption_algorithm_name="aes", encryption_algorithm_keylen=256,
            # phase1-only fields that used to be sent and dropped:
            hash_algorithm="hmac_sha256", dhgroup=14,
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/vpn/ipsec/phase2/encryption"
        assert data["name"] == "aes" and data["keylen"] == 256
        # the phase1-only fields must not be sent
        for stale in ("encryption_algorithm_name", "encryption_algorithm_keylen",
                      "hash_algorithm", "dhgroup", "prf_algorithm"):
            assert stale not in data

    async def test_update_uses_name_and_keylen(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_ipsec_phase2_encryption(
            encryption_id=3, encryption_algorithm_name="aes256gcm", encryption_algorithm_keylen=256,
        )
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["name"] == "aes256gcm" and data["keylen"] == 256
        assert "encryption_algorithm_name" not in data
