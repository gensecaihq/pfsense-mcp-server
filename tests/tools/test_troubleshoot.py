"""Tests for the health-diagnostics fixes (originally PR #21, completed).

Covers the three endpoint/shape corrections and — critically — that all three
gateway-checking diagnostics read runtime status from `/status/gateways` (the
`/routing/gateways` config endpoint has no `status` field, so it classified
every gateway as "unknown" and appended a false issue).
"""
from src.tools.troubleshoot import (
    diagnose_connectivity,
    diagnose_dns_resolution,
    diagnose_interface_issues,
    diagnose_service_health,
)


def _router(mapping):
    """Return an async side_effect that routes _make_request by endpoint."""
    async def route(*args, **kwargs):
        endpoint = kwargs.get("endpoint", args[1] if len(args) > 1 else "")
        for key, value in mapping.items():
            if key in endpoint:
                return value
        return {"data": []}
    return route


class TestGatewayStatus:
    async def test_connectivity_gateway_without_status_is_not_a_false_issue(
        self, mock_client, mock_make_request
    ):
        # A config-shaped gateway (no runtime `status`) must not produce a
        # "Gateway X is unknown" issue — the headline bug this PR fixes.
        mock_make_request.side_effect = _router({
            "/status/gateways": {"data": [
                {"name": "WAN_DHCP", "interface": "wan", "gateway": "1.1.1.1", "monitor": "1.1.1.1"},
            ]},
        })
        result = await diagnose_connectivity(host="8.8.8.8")
        assert result["gateway_status"][0]["status"] == "unknown"
        assert not any("unknown" in issue.lower() for issue in result["issues"])

    async def test_connectivity_flags_a_down_gateway(self, mock_client, mock_make_request):
        mock_make_request.side_effect = _router({
            "/status/gateways": {"data": [
                {"name": "WAN_DHCP", "interface": "wan", "gateway": "1.1.1.1", "status": "down"},
            ]},
        })
        result = await diagnose_connectivity(host="8.8.8.8")
        assert any("WAN_DHCP" in issue and "down" in issue for issue in result["issues"])

    async def test_connectivity_uses_status_endpoint_not_config(
        self, mock_client, mock_make_request
    ):
        mock_make_request.side_effect = _router({"/status/gateways": {"data": []}})
        await diagnose_connectivity(host="8.8.8.8")
        endpoints = [
            (c.kwargs.get("endpoint") or (c.args[1] if len(c.args) > 1 else ""))
            for c in mock_make_request.call_args_list
        ]
        assert "/status/gateways" in endpoints
        assert "/routing/gateways" not in endpoints

    async def test_interface_issues_reads_status_endpoint(self, mock_client, mock_make_request):
        mock_make_request.side_effect = _router({
            "/status/gateways": {"data": [
                {"name": "WAN_DHCP", "interface": "wan", "gateway": "1.1.1.1", "status": "down"},
            ]},
        })
        result = await diagnose_interface_issues(interface="wan")
        assert any("WAN_DHCP" in issue and "down" in issue for issue in result["issues"])
        endpoints = [
            (c.kwargs.get("endpoint") or (c.args[1] if len(c.args) > 1 else ""))
            for c in mock_make_request.call_args_list
        ]
        assert "/routing/gateways" not in endpoints


class TestServiceStatusNormalization:
    async def test_boolean_service_status(self, mock_client, mock_make_request):
        mock_make_request.side_effect = _router({
            "/status/services": {"data": [
                {"name": "dhcpd", "status": False, "description": "DHCP Server"},
                {"name": "unbound", "status": True, "description": "DNS Resolver"},
            ]},
        })
        result = await diagnose_service_health()
        assert "dhcpd" in result["services"]["stopped"]
        assert "unbound" in result["services"]["running"]
        # dhcpd is a critical service → flagged
        assert any("dhcpd" in issue for issue in result["issues"])


class TestDnsSource:
    async def test_reads_system_dns_endpoint(self, mock_client, mock_make_request):
        mock_make_request.side_effect = _router({
            "/system/dns": {"data": {"dnsserver": ["8.8.8.8", "1.1.1.1"]}},
        })
        result = await diagnose_dns_resolution()
        assert result["system_dns_servers"] == ["8.8.8.8", "1.1.1.1"]
