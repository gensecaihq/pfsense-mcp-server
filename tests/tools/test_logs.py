"""Unit tests for log tools (src/tools/logs.py)."""

import httpx
import pytest

from src.tools.logs import (
    _LOG_OOM_ERROR,
    _is_oom_error,
    analyze_blocked_traffic,
    get_firewall_log,
    search_logs_by_ip,
)

_get_firewall_log = get_firewall_log.fn
_analyze_blocked_traffic = analyze_blocked_traffic.fn
_search_logs_by_ip = search_logs_by_ip.fn


# ---------------------------------------------------------------------------
# get_firewall_log
# ---------------------------------------------------------------------------

class TestGetFirewallLog:
    async def test_default(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await _get_firewall_log()
        assert result["success"] is True
        assert result["count"] == 2

    async def test_lines_capped_at_50(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await _get_firewall_log(lines=200)
        assert result["lines_requested"] == 50

    async def test_filters(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await _get_firewall_log(
            action_filter="block", interface="wan",
            source_ip="203.0.113.5", protocol="tcp",
        )
        assert result["success"] is True
        assert result["filters_applied"]["action"] == "block"
        assert result["filters_applied"]["interface"] == "wan"

    async def test_destination_ip_filter(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await _get_firewall_log(destination_ip="192.168.1.1")
        assert result["success"] is True
        # Firewall log model only has 'text' field — client-side filtering on raw text
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "text" and f.value == "192.168.1.1" and f.operator == "contains" for f in filters)

    async def test_no_sort_sent(self, mock_client, mock_make_request, firewall_logs_response):
        """Log endpoints don't support sort_by — verify none is sent."""
        mock_make_request.return_value = firewall_logs_response
        await _get_firewall_log()
        call_kwargs = mock_make_request.call_args
        sort = call_kwargs.kwargs.get("sort") or call_kwargs[1].get("sort", None)
        assert sort is None

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("log fetch failed")
        result = await _get_firewall_log()
        assert result["success"] is False
        assert "log fetch failed" in result["error"]


# ---------------------------------------------------------------------------
# analyze_blocked_traffic
# ---------------------------------------------------------------------------

class TestAnalyzeBlockedTraffic:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("analysis failed")
        result = await _analyze_blocked_traffic()
        assert result["success"] is False
        assert "analysis failed" in result["error"]

    async def test_grouped(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await _analyze_blocked_traffic(group_by_source=True)
        assert result["success"] is True
        assert result["analysis"]["grouped_by"] == "source_ip"

    async def test_ungrouped(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await _analyze_blocked_traffic(group_by_source=False)
        assert result["success"] is True
        assert result["analysis"]["grouped_by"] == "none"
        assert "raw_entries" in result["analysis"]


# ---------------------------------------------------------------------------
# search_logs_by_ip
# ---------------------------------------------------------------------------

class TestSearchLogsByIp:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("search failed")
        result = await _search_logs_by_ip(ip_address="10.0.0.1")
        assert result["success"] is False
        assert "search failed" in result["error"]

    async def test_firewall_type(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await _search_logs_by_ip(ip_address="203.0.113.5", log_type="firewall")
        assert result["success"] is True
        assert result["ip_address"] == "203.0.113.5"
        assert result["patterns"] is not None

    async def test_non_firewall_type(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        result = await _search_logs_by_ip(ip_address="10.0.0.1", log_type="system")
        assert result["success"] is True
        assert result["log_type"] == "system"
        assert result["patterns"] is None

    async def test_non_firewall_lines_capped_at_50(self, mock_client, mock_make_request):
        """Non-firewall log requests should also be capped to prevent memory exhaustion."""
        mock_make_request.return_value = {"data": []}
        await _search_logs_by_ip(ip_address="10.0.0.1", log_type="system", lines=500)
        pagination = mock_make_request.call_args.kwargs.get("pagination")
        assert pagination is not None
        assert pagination.limit == 50


# ---------------------------------------------------------------------------
# _is_oom_error classifier
# ---------------------------------------------------------------------------

class TestIsOomError:
    """Verify _is_oom_error matches only read-phase failures."""

    @pytest.mark.parametrize("exc_cls", [
        httpx.ReadError,
        httpx.RemoteProtocolError,
        httpx.ReadTimeout,
    ])
    def test_matches_read_phase_errors(self, exc_cls):
        assert _is_oom_error(exc_cls("boom")) is True

    @pytest.mark.parametrize("exc_cls", [
        httpx.ConnectTimeout,
        httpx.ConnectError,
        httpx.PoolTimeout,
    ])
    def test_does_not_match_connect_pool_errors(self, exc_cls):
        assert _is_oom_error(exc_cls("boom")) is False

    def test_does_not_match_generic_exception(self):
        assert _is_oom_error(Exception("something else")) is False


# ---------------------------------------------------------------------------
# OOM error handling in each tool
# ---------------------------------------------------------------------------

class TestLogOomHandling:
    """All three log tools should return _LOG_OOM_ERROR on read-phase failures."""

    async def test_get_firewall_log_oom(self, mock_client, mock_make_request):
        mock_make_request.side_effect = httpx.ReadError("peer closed connection")
        result = await _get_firewall_log()
        assert result == _LOG_OOM_ERROR

    async def test_analyze_blocked_traffic_oom(self, mock_client, mock_make_request):
        mock_make_request.side_effect = httpx.ReadTimeout("read timed out")
        result = await _analyze_blocked_traffic()
        assert result == _LOG_OOM_ERROR

    async def test_search_logs_by_ip_oom(self, mock_client, mock_make_request):
        mock_make_request.side_effect = httpx.RemoteProtocolError("connection reset")
        result = await _search_logs_by_ip(ip_address="10.0.0.1")
        assert result == _LOG_OOM_ERROR

    async def test_non_oom_error_still_returned_normally(self, mock_client, mock_make_request):
        """A ConnectTimeout should NOT be mapped to the OOM error."""
        mock_make_request.side_effect = httpx.ConnectTimeout("connect timed out")
        result = await _get_firewall_log()
        assert result["success"] is False
        assert result != _LOG_OOM_ERROR
        assert "connect timed out" in result["error"]


# ---------------------------------------------------------------------------
# LOG_TIMEOUT passthrough
# ---------------------------------------------------------------------------

class TestLogTimeout:
    """Log client methods should pass LOG_TIMEOUT to _make_request."""

    async def test_get_firewall_logs_passes_timeout(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _get_firewall_log()
        assert mock_make_request.call_args.kwargs.get("timeout") == mock_client.LOG_TIMEOUT

    async def test_search_logs_by_ip_passes_timeout(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _search_logs_by_ip(ip_address="10.0.0.1", log_type="firewall")
        assert mock_make_request.call_args.kwargs.get("timeout") == mock_client.LOG_TIMEOUT

    async def test_get_logs_passes_timeout(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await _search_logs_by_ip(ip_address="10.0.0.1", log_type="system")
        assert mock_make_request.call_args.kwargs.get("timeout") == mock_client.LOG_TIMEOUT
