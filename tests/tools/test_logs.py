"""Unit tests for log tools (src/tools/logs.py)."""

import httpx
import pytest

from src.tools.logs import (
    _is_oom_error,
    analyze_blocked_traffic,
    get_firewall_log,
    get_log_file,
    search_logs_by_ip,
)

_get_firewall_log = get_firewall_log
_get_log_file = get_log_file
_analyze_blocked_traffic = analyze_blocked_traffic
_search_logs_by_ip = search_logs_by_ip


# ---------------------------------------------------------------------------
# OOM / read-phase failure handling (PR #6, pfSense-pkg-RESTAPI#806)
# ---------------------------------------------------------------------------

class TestLogOomHandling:
    def test_classifier_matches_read_phase_failures(self):
        assert _is_oom_error(httpx.ReadError("boom"))
        assert _is_oom_error(httpx.RemoteProtocolError("boom"))
        assert _is_oom_error(httpx.ReadTimeout("boom"))

    def test_classifier_ignores_unrelated_errors(self):
        assert not _is_oom_error(httpx.ConnectError("boom"))
        assert not _is_oom_error(ValueError("boom"))

    async def test_get_firewall_log_returns_oom_message(self, mock_client, mock_make_request):
        mock_make_request.side_effect = httpx.ReadError("server died")
        result = await _get_firewall_log()
        assert result["success"] is False
        assert "pfSense-pkg-RESTAPI#806" in result["error"]

    async def test_non_oom_error_passes_through(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("plain failure")
        result = await _get_firewall_log()
        assert result["success"] is False
        assert "plain failure" in result["error"]


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
        assert result["count"] == 1
        assert result["filters_applied"]["action"] == "block"
        assert result["filters_applied"]["interface"] == "wan"
        assert mock_make_request.call_args.kwargs.get("filters") is None

    async def test_destination_ip_filter(self, mock_client, mock_make_request, firewall_logs_response):
        mock_make_request.return_value = firewall_logs_response
        result = await _get_firewall_log(destination_ip="192.168.1.1")
        assert result["success"] is True
        # Firewall log filters run locally so the API returns the newest window.
        assert mock_make_request.call_args.kwargs.get("filters") is None

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
        assert result["total_entries_analyzed"] == 1
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
        assert result["total_entries"] == 1
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
# get_log_file (raw log-file reads via /diagnostics/command_prompt)
# ---------------------------------------------------------------------------

class TestGetLogFile:
    async def test_reads_resolver_log(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": {"output": "resolver line\n", "result_code": 0}
        }
        result = await _get_log_file(log_file="resolver")
        assert result["success"] is True
        assert result["log_file"] == "resolver"
        assert result["output"] == "resolver line\n"
        assert result["lines_requested"] == 100
        command = mock_make_request.call_args.kwargs["data"]["command"]
        assert command == "tail -n 100 /var/log/resolver.log"

    @pytest.mark.parametrize("log_file,path", [
        ("dhcpd", "/var/log/dhcpd.log"),
        ("filter", "/var/log/filter.log"),
        ("resolver", "/var/log/resolver.log"),
        ("system", "/var/log/system.log"),
        ("auth", "/var/log/auth.log"),
    ])
    async def test_allowlisted_paths(self, mock_client, mock_make_request, log_file, path):
        mock_make_request.return_value = {"data": {"output": "", "result_code": 0}}
        result = await _get_log_file(log_file=log_file)
        assert result["success"] is True
        assert mock_make_request.call_args.kwargs["data"]["command"] == f"tail -n 100 {path}"

    async def test_rejects_non_allowlisted_file(self, mock_client, mock_make_request):
        result = await _get_log_file(log_file="../../config.xml")
        assert result["success"] is False
        assert "Allowed" in result["error"]
        mock_make_request.assert_not_called()

    async def test_lines_capped_at_1000(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"output": "", "result_code": 0}}
        result = await _get_log_file(log_file="system", lines=99999)
        command = mock_make_request.call_args.kwargs["data"]["command"]
        assert command == "tail -n 1000 /var/log/system.log"
        assert result["lines_requested"] == 1000

    async def test_lines_floored_at_1(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"output": "", "result_code": 0}}
        result = await _get_log_file(log_file="system", lines=0)
        command = mock_make_request.call_args.kwargs["data"]["command"]
        assert command == "tail -n 1 /var/log/system.log"
        assert result["lines_requested"] == 1

    async def test_grep_is_shell_escaped(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"output": "", "result_code": 0}}
        await _get_log_file(log_file="filter", grep="bad; rm -rf /")
        command = mock_make_request.call_args.kwargs["data"]["command"]
        # The injection attempt must arrive as a single quoted grep argument
        assert command == (
            "set -o pipefail; "
            "{ grep -F -e 'bad; rm -rf /' /var/log/filter.log | tail -n 100; }"
        )

    async def test_grep_runs_before_tail(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"output": "", "result_code": 0}}
        await _get_log_file(log_file="dhcpd", grep="192.168.1.50", lines=20)
        command = mock_make_request.call_args.kwargs["data"]["command"]
        assert command == (
            "set -o pipefail; "
            "{ grep -F -e 192.168.1.50 /var/log/dhcpd.log | tail -n 20; }"
        )

    async def test_nonzero_result_code_is_a_failure(self, mock_client, mock_make_request):
        """stderr is merged into `output`; a failed read must not look successful."""
        mock_make_request.return_value = {
            "data": {
                "output": "tail: /var/log/resolver.log: No such file or directory",
                "result_code": 1,
            }
        }
        result = await _get_log_file(log_file="resolver")
        assert result["success"] is False
        assert result["result_code"] == 1
        assert "No such file" in result["error"]

    async def test_empty_output_with_zero_exit_is_success(
        self, mock_client, mock_make_request
    ):
        """grep matching nothing is an empty result, not an error."""
        mock_make_request.return_value = {"data": {"output": "", "result_code": 0}}
        result = await _get_log_file(log_file="filter", grep="nothing-matches")
        assert result["success"] is True
        assert result["output"] == ""

    async def test_grep_no_match_exit_is_success(self, mock_client, mock_make_request):
        """Under pipefail grep's exit 1 reaches us; it still means "no matches"."""
        mock_make_request.return_value = {"data": {"output": "", "result_code": 1}}
        result = await _get_log_file(log_file="filter", grep="nothing-matches")
        assert result["success"] is True
        assert result["output"] == ""

    async def test_grep_read_error_is_a_failure(self, mock_client, mock_make_request):
        """A grep that can't read the file must not pass as an empty result.

        Regression guard for the bare pipeline: `grep ... | tail` reported the
        exit status of tail, so a missing file arrived as exit 0 with no
        output. Grouping the pipeline under pipefail surfaces grep's 2 and its
        stderr instead.
        """
        mock_make_request.return_value = {
            "data": {
                "output": "grep: /var/log/resolver.log: No such file or directory",
                "result_code": 2,
            }
        }
        result = await _get_log_file(log_file="resolver", grep="SERVFAIL")
        assert result["success"] is False
        assert result["result_code"] == 2
        assert "No such file" in result["error"]

    async def test_exit_one_without_grep_is_still_a_failure(
        self, mock_client, mock_make_request
    ):
        """Only grep gets the no-match exemption; a lone tail's 1 is an error."""
        mock_make_request.return_value = {
            "data": {
                "output": "tail: /var/log/dhcpd.log: No such file or directory",
                "result_code": 1,
            }
        }
        result = await _get_log_file(log_file="dhcpd")
        assert result["success"] is False
        assert result["result_code"] == 1

    async def test_missing_result_code_is_tolerated(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"output": "line"}}
        result = await _get_log_file(log_file="system")
        assert result["success"] is True
        assert result["output"] == "line"

    async def test_non_dict_response_does_not_raise(self, mock_client, mock_make_request):
        """_make_request returns response.json() verbatim — it needn't be an object."""
        mock_make_request.return_value = "raw log text"
        result = await _get_log_file(log_file="system")
        assert result["success"] is True
        assert result["output"] == "raw log text"

    async def test_api_error_passes_through(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("command sink failed")
        result = await _get_log_file(log_file="system")
        assert result["success"] is False
        assert "command sink failed" in result["error"]
