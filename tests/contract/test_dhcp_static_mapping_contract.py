"""Contract tests for per-host DHCP lease times on static mappings.

``defaultleasetime`` and ``maxleasetime`` are declared on the v2.10.2
DHCPServerStaticMapping model for both POST and PATCH, typed integer. The
framework silently drops unknown request keys, so a misspelled field name here
would look like success while the reservation kept the package defaults. These
assert the wire names and types against the vendored contract.
"""
from src.tools.dhcp import create_dhcp_static_mapping, update_dhcp_static_mapping
from tests.contract.schema import assert_payload_valid, capture_call


class TestStaticMappingLeaseTimes:
    async def test_create_sends_contract_field_names(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_dhcp_static_mapping(
            interface="lan", mac_address="00:11:22:33:44:55",
            ip_address="192.168.1.50",
            default_lease_time=86400, max_lease_time=172800,
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, _, data = capture_call(mock_make_request)
        assert data["defaultleasetime"] == 86400
        assert data["maxleasetime"] == 172800

    async def test_update_sends_contract_field_names(self, mock_client, mock_make_request):
        mock_make_request.side_effect = [
            {"data": [{"id": "lan", "staticmap": [{"id": 0, "parent_id": "lan"}]}]},
            {"data": {}},
        ]
        result = await update_dhcp_static_mapping(
            mapping_id=0, default_lease_time=43200, max_lease_time=86400
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["defaultleasetime"] == 43200
        assert data["maxleasetime"] == 86400
