"""Unit tests for system tools (src/tools/system.py)."""

from src.tools.system import find_interfaces_by_status, system_status

_system_status = system_status.fn
_find_interfaces_by_status = find_interfaces_by_status.fn


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

class TestFindInterfacesByStatus:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [{"name": "wan", "status": "up"}],
        }
        result = await _find_interfaces_by_status(status="up")
        assert result["success"] is True
        assert result["status_filter"] == "up"
        assert result["count"] == 1
