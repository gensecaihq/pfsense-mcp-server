"""Unit tests for system tools (src/tools/system.py)."""

from src.tools.system import (
    find_interfaces_by_status,
    get_arp_table,
    search_interfaces,
    system_status,
)

_system_status = system_status.fn
_find_interfaces_by_status = find_interfaces_by_status.fn
_search_interfaces = search_interfaces.fn
_get_arp_table = get_arp_table.fn


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------

class TestSystemStatus:
    async def test_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": {"cpu_usage": "5%", "memory_usage": "40%"},
        }
        result = await _system_status()
        assert result["success"] is True
        assert "cpu_usage" in result["data"]

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("connection refused")
        result = await _system_status()
        assert result["success"] is False
        assert "connection refused" in result["error"]


# ---------------------------------------------------------------------------
# find_interfaces_by_status
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# search_interfaces
# ---------------------------------------------------------------------------

class TestSearchInterfaces:
    async def test_no_filters(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": [{"name": "wan", "status": "up"}]}
        result = await _search_interfaces()
        assert result["success"] is True
        assert result["page"] == 1
        assert result["page_size"] == 20

    async def test_search_term_filter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _search_interfaces(search_term="wan")
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "name" and f.value == "wan" and f.operator == "contains" for f in filters)

    async def test_status_filter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _search_interfaces(status_filter="up")
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "status" and f.value == "up" for f in filters)

    async def test_both_filters(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _search_interfaces(search_term="wan", status_filter="up")
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert len(filters) == 2

    async def test_pagination_forwarded(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        result = await _search_interfaces(page=3, page_size=5)
        assert result["page"] == 3
        assert result["page_size"] == 5

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("timeout")
        result = await _search_interfaces()
        assert result["success"] is False
        assert "timeout" in result["error"]


# ---------------------------------------------------------------------------
# find_interfaces_by_status
# ---------------------------------------------------------------------------

class TestFindInterfacesByStatus:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("status failed")
        result = await _find_interfaces_by_status(status="up")
        assert result["success"] is False
        assert "status failed" in result["error"]

    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [{"name": "wan", "status": "up"}],
        }
        result = await _find_interfaces_by_status(status="up")
        assert result["success"] is True
        assert result["status_filter"] == "up"
        assert result["count"] == 1


# ---------------------------------------------------------------------------
# get_arp_table
# ---------------------------------------------------------------------------

class TestGetArpTable:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [
                {"ip": "192.168.1.1", "mac": "aa:bb:cc:dd:ee:01", "interface": "lan"},
                {"ip": "192.168.1.100", "mac": "aa:bb:cc:dd:ee:02", "interface": "lan"},
            ]
        }
        result = await _get_arp_table()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_ip_filter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _get_arp_table(ip_address="192.168.1")
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "ip_address" and f.value == "192.168.1" and f.operator == "contains" for f in filters)

    async def test_mac_filter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _get_arp_table(mac_address="aa:bb")
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "mac_address" and f.value == "aa:bb" for f in filters)

    async def test_interface_filter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _get_arp_table(interface="opt1")
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "interface" and f.value == "opt1" for f in filters)

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("arp failed")
        result = await _get_arp_table()
        assert result["success"] is False
