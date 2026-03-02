"""Unit tests for DHCP tools (src/tools/dhcp.py)."""

from src.tools.dhcp import (
    create_dhcp_static_mapping,
    delete_dhcp_static_mapping,
    search_dhcp_leases,
    search_dhcp_static_mappings,
    update_dhcp_static_mapping,
)

_search_dhcp_leases = search_dhcp_leases.fn
_search_dhcp_static_mappings = search_dhcp_static_mappings.fn
_create_dhcp_static_mapping = create_dhcp_static_mapping.fn
_update_dhcp_static_mapping = update_dhcp_static_mapping.fn
_delete_dhcp_static_mapping = delete_dhcp_static_mapping.fn


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


# ---------------------------------------------------------------------------
# search_dhcp_static_mappings
# ---------------------------------------------------------------------------

class TestSearchDhcpStaticMappings:
    async def test_no_filters(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await _search_dhcp_static_mappings()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_interface_filter(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await _search_dhcp_static_mappings(interface="lan")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "parent_id" and f.value == "lan" for f in filters)

    async def test_mac_filter(self, mock_client, mock_make_request, dhcp_static_mappings_response):
        mock_make_request.return_value = dhcp_static_mappings_response
        result = await _search_dhcp_static_mappings(mac_address="aa:bb:cc:dd:ee:01")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "mac" for f in filters)


# ---------------------------------------------------------------------------
# create_dhcp_static_mapping
# ---------------------------------------------------------------------------

class TestCreateDhcpStaticMapping:
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
    async def test_partial_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _update_dhcp_static_mapping(mapping_id=0, hostname="newhostname")
        assert result["success"] is True
        assert "hostname" in result["fields_updated"]

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await _update_dhcp_static_mapping(mapping_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]


# ---------------------------------------------------------------------------
# delete_dhcp_static_mapping
# ---------------------------------------------------------------------------

class TestDeleteDhcpStaticMapping:
    async def test_passes_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _delete_dhcp_static_mapping(mapping_id=3)
        assert result["success"] is True
        assert result["mapping_id"] == 3
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 3
