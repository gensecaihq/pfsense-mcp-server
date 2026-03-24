"""Unit tests for DHCP tools (src/tools/dhcp.py)."""

from src.tools.dhcp import (
    create_dhcp_static_mapping,
    delete_dhcp_static_mapping,
    get_dhcp_server_config,
    search_dhcp_leases,
    search_dhcp_static_mappings,
    update_dhcp_server_config,
    update_dhcp_static_mapping,
)

_search_dhcp_leases = search_dhcp_leases.fn
_search_dhcp_static_mappings = search_dhcp_static_mappings.fn
_create_dhcp_static_mapping = create_dhcp_static_mapping.fn
_update_dhcp_static_mapping = update_dhcp_static_mapping.fn
_delete_dhcp_static_mapping = delete_dhcp_static_mapping.fn
_get_dhcp_server_config = get_dhcp_server_config.fn
_update_dhcp_server_config = update_dhcp_server_config.fn


# ---------------------------------------------------------------------------
# search_dhcp_leases — includes regression test for double-filter bug
# ---------------------------------------------------------------------------

class TestSearchDhcpLeases:
    async def test_basic(self, mock_client, mock_make_request, dhcp_leases_response):
        mock_make_request.return_value = dhcp_leases_response
        result = await _search_dhcp_leases()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_interface_filter_appears_once(
        self, mock_client, mock_make_request, dhcp_leases_response
    ):
        """Regression: interface must NOT be passed both via filters AND
        as keyword arg to get_dhcp_leases (which would add it again)."""
        mock_make_request.return_value = dhcp_leases_response
        await _search_dhcp_leases(interface="lan")

        # get_dhcp_leases delegates to _make_request. Inspect the filters
        # that _make_request received — "if" should appear exactly once.
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters") or []
        if_count = sum(1 for f in filters if f.field == "if")
        assert if_count == 1, f"Expected 1 'if' filter, got {if_count}"

    async def test_search_term_filter(self, mock_client, mock_make_request, dhcp_leases_response):
        """search_term does client-side filtering on hostname, IP, and MAC."""
        mock_make_request.return_value = dhcp_leases_response
        result = await _search_dhcp_leases(search_term="laptop")
        # Should match the "laptop" lease via hostname
        assert result["count"] == 1
        assert result["leases"][0]["hostname"] == "laptop"

    async def test_search_term_matches_ip(self, mock_client, mock_make_request, dhcp_leases_response):
        """search_term should also match IP addresses."""
        mock_make_request.return_value = dhcp_leases_response
        result = await _search_dhcp_leases(search_term="192.168.1.100")
        assert result["count"] == 1
        assert result["leases"][0]["ip"] == "192.168.1.100"

    async def test_hostname_filter(self, mock_client, mock_make_request, dhcp_leases_response):
        mock_make_request.return_value = dhcp_leases_response
        await _search_dhcp_leases(hostname="desktop")
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "hostname" and f.value == "desktop" and f.operator == "contains" for f in filters)

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("DHCP error")
        result = await _search_dhcp_leases()
        assert result["success"] is False
        assert "DHCP error" in result["error"]


# ---------------------------------------------------------------------------
# search_dhcp_static_mappings
# ---------------------------------------------------------------------------

class TestSearchDhcpStaticMappings:
    async def test_no_filters(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await _search_dhcp_static_mappings()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_interface_passed_as_extra_param(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        """Interface should be passed as parent_id query param, not a filter."""
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await _search_dhcp_static_mappings(interface="lan")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        extra = call_kwargs.kwargs.get("extra_params") or call_kwargs[1].get("extra_params")
        assert extra == {"parent_id": "lan"}
        # Verify parent_id is NOT in filters
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        if filters:
            assert not any(f.field == "parent_id" for f in filters)

    async def test_mac_filter(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await _search_dhcp_static_mappings(mac_address="aa:bb:cc:dd:ee:01")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "mac" for f in filters)

    async def test_hostname_filter(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await _search_dhcp_static_mappings(hostname="server")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "hostname" and f.value == "server" and f.operator == "contains" for f in filters)

    async def test_ip_address_filter(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await _search_dhcp_static_mappings(ip_address="192.168.1.200")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "ipaddr" and f.value == "192.168.1.200" for f in filters)

    async def test_404_returns_empty_for_non_lan_interface(self, mock_client, mock_make_request):
        """404 for non-LAN interfaces should return empty results, not an error."""
        mock_make_request.side_effect = Exception("Status: 404\nURL: .../static_mappings")
        result = await _search_dhcp_static_mappings(interface="opt1")
        assert result["success"] is True
        assert result["count"] == 0
        assert result["static_mappings"] == []
        assert "DHCP may not be enabled" in result.get("message", "")

    async def test_404_with_default_interface(self, mock_client, mock_make_request):
        """404 with default interface returns empty (DHCP may not be enabled)."""
        mock_make_request.side_effect = Exception("Status: 404")
        result = await _search_dhcp_static_mappings()
        assert result["success"] is True
        assert result["count"] == 0
        assert "DHCP may not be enabled" in result.get("message", "")


# ---------------------------------------------------------------------------
# create_dhcp_static_mapping
# ---------------------------------------------------------------------------

class TestCreateDhcpStaticMapping:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("create failed")
        result = await _create_dhcp_static_mapping(
            interface="lan", mac_address="aa:bb:cc:dd:ee:03", ip_address="192.168.1.202"
        )
        assert result["success"] is False
        assert "create failed" in result["error"]

    async def test_required_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _create_dhcp_static_mapping(
            interface="lan", mac_address="aa:bb:cc:dd:ee:03", ip_address="192.168.1.202"
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["parent_id"] == "lan"
        assert data["mac"] == "aa:bb:cc:dd:ee:03"
        assert data["ipaddr"] == "192.168.1.202"

    async def test_all_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await _create_dhcp_static_mapping(
            interface="lan", mac_address="aa:bb:cc:dd:ee:04",
            ip_address="192.168.1.203", hostname="myhost",
            description="Test mapping", dns_server="8.8.8.8",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["hostname"] == "myhost"
        assert data["descr"] == "Test mapping"
        assert data["dnsserver"] == "8.8.8.8"


# ---------------------------------------------------------------------------
# update_dhcp_static_mapping
# ---------------------------------------------------------------------------

class TestUpdateDhcpStaticMapping:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("update failed")
        result = await _update_dhcp_static_mapping(mapping_id=0, hostname="x")
        assert result["success"] is False
        assert "update failed" in result["error"]

    async def test_partial_update(self, mock_client, mock_make_request):
        # First call: lookup parent_id; second call: the PATCH
        mock_make_request.side_effect = [
            {"data": [{"id": 0, "parent_id": "lan", "mac": "aa:bb:cc:dd:ee:01"}]},
            {"data": {"id": 0}},
        ]
        result = await _update_dhcp_static_mapping(mapping_id=0, hostname="newhostname")
        assert result["success"] is True
        assert "hostname" in result["fields_updated"]
        # Verify parent_id was included in the PATCH request
        patch_call = mock_make_request.call_args_list[1]
        data = patch_call.kwargs.get("data") or patch_call[1].get("data")
        assert data["parent_id"] == "lan"

    async def test_explicit_interface_skips_lookup(self, mock_client, mock_make_request):
        """When interface is provided, no lookup call is needed."""
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _update_dhcp_static_mapping(
            mapping_id=0, hostname="newhostname", interface="opt1"
        )
        assert result["success"] is True
        # Only one call (the PATCH), no lookup
        assert mock_make_request.call_count == 1
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["parent_id"] == "opt1"

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await _update_dhcp_static_mapping(mapping_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]


# ---------------------------------------------------------------------------
# delete_dhcp_static_mapping
# ---------------------------------------------------------------------------

class TestDeleteDhcpStaticMapping:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("delete failed")
        result = await _delete_dhcp_static_mapping(mapping_id=3, interface="lan", confirm=True)
        assert result["success"] is False
        assert "delete failed" in result["error"]

    async def test_passes_id_and_parent_id(self, mock_client, mock_make_request):
        # First call: lookup parent_id; second call: the DELETE
        mock_make_request.side_effect = [
            {"data": [{"id": 3, "parent_id": "lan", "mac": "aa:bb:cc:dd:ee:03"}]},
            {"data": {}},
        ]
        result = await _delete_dhcp_static_mapping(mapping_id=3, confirm=True)
        assert result["success"] is True
        assert result["mapping_id"] == 3
        assert "note" in result  # ID shift warning
        assert "warning" in result  # auto-detected parent_id warning
        delete_call = mock_make_request.call_args_list[1]
        data = delete_call.kwargs.get("data") or delete_call[1].get("data")
        assert data["id"] == 3
        assert data["parent_id"] == "lan"

    async def test_explicit_interface_skips_lookup(self, mock_client, mock_make_request):
        """When interface is provided, no lookup call is needed."""
        mock_make_request.return_value = {"data": {}}
        result = await _delete_dhcp_static_mapping(mapping_id=3, interface="opt1", confirm=True)
        assert result["success"] is True
        assert mock_make_request.call_count == 1
        assert "warning" not in result  # no auto-detection warning
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 3
        assert data["parent_id"] == "opt1"

    async def test_confirm_required(self, mock_client, mock_make_request):
        result = await _delete_dhcp_static_mapping(mapping_id=3, interface="lan")
        assert result["success"] is False
        assert "confirm" in result["error"].lower()


# ---------------------------------------------------------------------------
# get_dhcp_server_config
# ---------------------------------------------------------------------------

class TestGetDhcpServerConfig:
    async def test_no_filter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [
                {"id": 0, "interface": "lan", "range_from": "192.168.1.100", "range_to": "192.168.1.200"},
                {"id": 1, "interface": "opt1", "range_from": "10.0.0.100", "range_to": "10.0.0.200"},
            ]
        }
        result = await _get_dhcp_server_config()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_interface_filter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [{"id": 0, "interface": "lan", "range_from": "192.168.1.100"}]
        }
        result = await _get_dhcp_server_config(interface="lan")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters")
        assert any(f.field == "id" and f.value == "lan" for f in filters)

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("not found")
        result = await _get_dhcp_server_config()
        assert result["success"] is False


# ---------------------------------------------------------------------------
# update_dhcp_server_config
# ---------------------------------------------------------------------------

class TestUpdateDhcpServerConfig:
    async def test_update_pool_range(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": "lan"}}
        result = await _update_dhcp_server_config(
            interface="lan", range_from="192.168.1.2", range_to="192.168.1.44"
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["range_from"] == "192.168.1.2"
        assert data["range_to"] == "192.168.1.44"
        assert data["id"] == "lan"

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await _update_dhcp_server_config(interface="lan")
        assert result["success"] is False
        assert "No fields" in result["error"]

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("update failed")
        result = await _update_dhcp_server_config(interface="lan", range_from="10.0.0.2")
        assert result["success"] is False
