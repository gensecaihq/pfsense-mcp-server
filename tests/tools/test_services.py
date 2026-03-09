"""Unit tests for service tools (src/tools/services.py)."""

from src.tools.services import control_service, search_services

_search_services = search_services.fn
_control_service = control_service.fn


# ---------------------------------------------------------------------------
# search_services
# ---------------------------------------------------------------------------

class TestSearchServices:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("service error")
        result = await _search_services()
        assert result["success"] is False
        assert "service error" in result["error"]

    async def test_no_filters(self, mock_client, mock_make_request, services_response):
        mock_make_request.return_value = services_response
        result = await _search_services()
        assert result["success"] is True
        assert result["count"] == 3

    async def test_running_filter(self, mock_client, mock_make_request, services_response):
        mock_make_request.return_value = services_response
        result = await _search_services(status_filter="running")
        assert result["success"] is True
        mock_make_request.assert_called_once()
        # Verify it called find_running_services path (GET /status/services with running filter)
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "status" and f.value == "running" for f in filters)

    async def test_stopped_filter(self, mock_client, mock_make_request, services_response):
        mock_make_request.return_value = services_response
        result = await _search_services(status_filter="stopped")
        assert result["success"] is True
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "status" and f.value == "stopped" for f in filters)

    async def test_search_term_with_status(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "status": "ok",
            "code": 200,
            "data": [
                {"name": "dhcpd", "description": "DHCP Server", "status": "running"},
                {"name": "unbound", "description": "DNS Resolver", "status": "running"},
            ],
        }
        result = await _search_services(search_term="dhcp", status_filter="running")
        assert result["success"] is True
        # In-memory filter should narrow to just dhcpd
        assert result["count"] == 1
        assert result["services"][0]["name"] == "dhcpd"


# ---------------------------------------------------------------------------
# control_service
# ---------------------------------------------------------------------------

class TestControlService:
    async def test_start(self, mock_client, mock_make_request, service_control_response):
        mock_make_request.return_value = service_control_response
        result = await _control_service(service_name="dhcpd", action="start")
        assert result["success"] is True
        assert result["action"] == "start"
        mock_make_request.assert_called_once()

    async def test_stop(self, mock_client, mock_make_request, service_control_response):
        mock_make_request.return_value = service_control_response
        result = await _control_service(service_name="dhcpd", action="stop")
        assert result["success"] is True
        assert result["action"] == "stop"

    async def test_restart(self, mock_client, mock_make_request, service_control_response):
        mock_make_request.return_value = service_control_response
        result = await _control_service(service_name="dhcpd", action="restart")
        assert result["success"] is True
        assert result["action"] == "restart"

    async def test_uppercase_action_normalization(self, mock_client, mock_make_request, service_control_response):
        mock_make_request.return_value = service_control_response
        result = await _control_service(service_name="dhcpd", action="START")
        assert result["success"] is True
        assert result["action"] == "start"

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("service unavailable")
        result = await _control_service(service_name="dhcpd", action="restart")
        assert result["success"] is False
        assert "service unavailable" in result["error"]

    async def test_invalid_action(self, mock_client, mock_make_request):
        result = await _control_service(service_name="dhcpd", action="purge")
        assert result["success"] is False
        assert "Invalid action" in result["error"]
