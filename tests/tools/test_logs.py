"""Unit tests for log tools (src/tools/logs.py)."""

from src.tools.logs import analyze_blocked_traffic, get_firewall_log, search_logs_by_ip

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


# ---------------------------------------------------------------------------
# analyze_blocked_traffic
# ---------------------------------------------------------------------------

class TestAnalyzeBlockedTraffic:
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
