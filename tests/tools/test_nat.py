"""Unit tests for NAT tools (src/tools/nat.py)."""

from src.tools.nat import (
    create_nat_port_forward,
    delete_nat_port_forward,
    search_nat_port_forwards,
    update_nat_port_forward,
)

_search_nat_port_forwards = search_nat_port_forwards.fn
_create_nat_port_forward = create_nat_port_forward.fn
_delete_nat_port_forward = delete_nat_port_forward.fn
_update_nat_port_forward = update_nat_port_forward.fn


# ---------------------------------------------------------------------------
# search_nat_port_forwards
# ---------------------------------------------------------------------------

class TestSearchNatPortForwards:
    async def test_basic(self, mock_client, mock_make_request, nat_forwards_response):
        mock_make_request.return_value = nat_forwards_response
        result = await _search_nat_port_forwards()
        assert result["success"] is True
        assert result["count"] == 1

    async def test_filters(self, mock_client, mock_make_request, nat_forwards_response):
        mock_make_request.return_value = nat_forwards_response
        result = await _search_nat_port_forwards(interface="wan", protocol="tcp")
        assert result["success"] is True
        assert result["filters_applied"]["interface"] == "wan"
        assert result["filters_applied"]["protocol"] == "tcp"

    async def test_destination_port_filter(self, mock_client, mock_make_request, nat_forwards_response):
        mock_make_request.return_value = nat_forwards_response
        result = await _search_nat_port_forwards(destination_port="8080")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "destination_port" and f.value == "8080" for f in filters)

    async def test_search_description_filter(self, mock_client, mock_make_request, nat_forwards_response):
        mock_make_request.return_value = nat_forwards_response
        result = await _search_nat_port_forwards(search_description="Web")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "descr" and f.value == "Web" and f.operator == "contains" for f in filters)

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("NAT error")
        result = await _search_nat_port_forwards()
        assert result["success"] is False
        assert "NAT error" in result["error"]


# ---------------------------------------------------------------------------
# create_nat_port_forward
# ---------------------------------------------------------------------------

class TestCreateNatPortForward:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("create failed")
        result = await _create_nat_port_forward(
            interface="wan", protocol="tcp", destination="wanip",
            destination_port="8080", target="192.168.1.50", local_port="80",
        )
        assert result["success"] is False
        assert "create failed" in result["error"]

    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await _create_nat_port_forward(
            interface="wan", protocol="tcp", destination="wanip",
            destination_port="8080", target="192.168.1.50", local_port="80",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["target"] == "192.168.1.50"

    async def test_associated_rule_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        await _create_nat_port_forward(
            interface="wan", protocol="tcp", destination="wanip",
            destination_port="443", target="192.168.1.50", local_port="443",
            create_associated_rule=False,
        )
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["associated_rule_id"] == ""

    async def test_nat_reflection_parameter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 2}}
        result = await _create_nat_port_forward(
            interface="wan", protocol="tcp", destination="wanip",
            destination_port="443", target="192.168.1.50", local_port="443",
            nat_reflection="purenat",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["natreflection"] == "purenat"

    async def test_rejects_invalid_destination_port(self, mock_client, mock_make_request):
        result = await _create_nat_port_forward(
            interface="wan", protocol="tcp", destination="wanip",
            destination_port="53 853", target="192.168.1.50", local_port="80",
        )
        assert result["success"] is False
        assert "Invalid destination_port" in result["error"]
        mock_make_request.assert_not_called()

    async def test_rejects_invalid_local_port(self, mock_client, mock_make_request):
        result = await _create_nat_port_forward(
            interface="wan", protocol="tcp", destination="wanip",
            destination_port="80", target="192.168.1.50", local_port="80, 443",
        )
        assert result["success"] is False
        assert "Invalid local_port" in result["error"]
        mock_make_request.assert_not_called()


# ---------------------------------------------------------------------------
# delete_nat_port_forward
# ---------------------------------------------------------------------------

class TestDeleteNatPortForward:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("delete failed")
        result = await _delete_nat_port_forward(port_forward_id=3)
        assert result["success"] is False
        assert "delete failed" in result["error"]

    async def test_passes_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _delete_nat_port_forward(port_forward_id=3)
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 3


# ---------------------------------------------------------------------------
# update_nat_port_forward
# ---------------------------------------------------------------------------

class TestUpdateNatPortForward:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("update failed")
        result = await _update_nat_port_forward(port_forward_id=0, target="10.0.0.1")
        assert result["success"] is False
        assert "update failed" in result["error"]

    async def test_basic_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _update_nat_port_forward(
            port_forward_id=0, target="192.168.1.60", local_port="8080"
        )
        assert result["success"] is True
        assert "target" in result["fields_updated"]
        assert "local_port" in result["fields_updated"]

    async def test_partial_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await _update_nat_port_forward(port_forward_id=1, description="new desc")
        assert result["success"] is True
        assert "descr" in result["fields_updated"]

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await _update_nat_port_forward(port_forward_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]

    async def test_interface_is_plain_string(self, mock_client, mock_make_request):
        """NAT PortForward uses a single string for interface, not an array."""
        mock_make_request.return_value = {"data": {"id": 0}}
        await _update_nat_port_forward(port_forward_id=0, interface="lan")
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["interface"] == "lan"

    async def test_rejects_invalid_port(self, mock_client, mock_make_request):
        result = await _update_nat_port_forward(port_forward_id=0, destination_port="53 853")
        assert result["success"] is False
        assert "Invalid destination_port" in result["error"]
        mock_make_request.assert_not_called()
