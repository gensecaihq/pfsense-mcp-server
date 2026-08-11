"""Contract tests for the DNS/DHCP silent-drop wire fixes.

Each drives a real tool through the mocked client and asserts the payload it
puts on the wire matches the pfSense v2.10.0 model contract. Before the fixes
these failed: DNS resolver sent register_dhcp/register_dhcp_static (upstream
regdhcp/regdhcpstatic), DHCP sent dnsserver as a bare string (upstream array),
and the access-list tools sent aclname/aclaction/descr (upstream
name/action/description with space-separated action values).
"""
from src.tools.dhcp import create_dhcp_static_mapping, update_dhcp_server_config
from src.tools.dns_resolver import (
    create_dns_access_list,
    update_dns_access_list,
    update_dns_resolver_settings,
)
from tests.contract.schema import assert_payload_valid, capture_call


class TestDnsResolverSettings:
    async def test_dhcp_registration_uses_regdhcp_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await update_dns_resolver_settings(
            register_dhcp=True, register_dhcp_static=True
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data == {"regdhcp": True, "regdhcpstatic": True}


class TestDhcpDnsServer:
    async def test_static_mapping_dnsserver_is_array(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_dhcp_static_mapping(
            interface="lan", mac_address="00:11:22:33:44:55",
            ip_address="192.168.1.50", dns_server="192.168.1.1, 1.1.1.1",
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["dnsserver"] == ["192.168.1.1", "1.1.1.1"]

    async def test_server_config_dnsserver_is_array(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await update_dhcp_server_config(interface="lan", dns_server="9.9.9.9")
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["dnsserver"] == ["9.9.9.9"]

    async def test_invalid_dns_server_is_rejected(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_dhcp_static_mapping(
            interface="lan", mac_address="00:11:22:33:44:55",
            ip_address="192.168.1.50", dns_server="not-an-ip",
        )
        assert result["success"] is False


class TestDnsAccessList:
    async def test_create_uses_name_action_description(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_dns_access_list(
            aclname="lan-acl", aclaction="allow_snoop", descr="LAN",
            networks=[{"network": "192.168.1.0", "mask": 24}],
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["name"] == "lan-acl"
        assert data["action"] == "allow snoop"  # space-separated wire value
        assert data["description"] == "LAN"
        assert "aclname" not in data and "aclaction" not in data

    async def test_update_maps_fields_and_action(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await update_dns_access_list(
            access_list_id=3, aclaction="deny_nonlocal", descr="blocked"
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["action"] == "deny nonlocal"
        assert data["description"] == "blocked"

    async def test_invalid_action_rejected(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_dns_access_list(aclname="x", aclaction="bogus")
        assert result["success"] is False
