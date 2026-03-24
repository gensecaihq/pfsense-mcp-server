"""Shared fixtures for pfSense MCP server tests."""

import os
from unittest.mock import AsyncMock, patch

import pytest

# Force test env vars — override any real values to prevent leaking
# real credentials into tests
os.environ["PFSENSE_URL"] = "https://192.0.2.1"
os.environ["PFSENSE_API_KEY"] = "test-key"
os.environ["AUTH_METHOD"] = "api_key"
os.environ["VERIFY_SSL"] = "false"

from src.pfsense_api_enhanced import (  # noqa: E402
    AuthMethod,
    EnhancedPfSenseAPIClient,
    PfSenseVersion,
)


@pytest.fixture(autouse=True)
def _reset_guardrail_rate_limiters():
    """Reset guardrail rate limiters between tests to prevent cross-test interference."""
    from src.guardrails import reset_rate_limiters
    reset_rate_limiters()
    yield
    reset_rate_limiters()


@pytest.fixture()
def mock_make_request():
    """Patch _make_request on the client class and return the AsyncMock."""
    with patch.object(
        EnhancedPfSenseAPIClient, "_make_request", new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.fixture()
def mock_client(mock_make_request):
    """Return a real client whose _make_request is already mocked.

    Also installs it as the global ``api_client`` used by the MCP tools in
    ``src.main`` so tool functions can be called directly.
    """
    import src.server as server_mod

    client = EnhancedPfSenseAPIClient(
        host="https://192.0.2.1",
        auth_method=AuthMethod.API_KEY,
        api_key="test-key",
        verify_ssl=False,
        version=PfSenseVersion.CE_2_8_0,
    )
    # Replace the instance method with the class-level mock
    client._make_request = mock_make_request
    server_mod.api_client = client
    yield client
    server_mod.api_client = None


# ---------------------------------------------------------------------------
# Response factories
# ---------------------------------------------------------------------------

@pytest.fixture()
def firewall_rules_response():
    return {
        "status": "ok",
        "code": 200,
        "data": [
            {
                "id": 0,
                "tracker": 1234567890,
                "type": "pass",
                "interface": ["lan"],
                "ipprotocol": "inet",
                "protocol": "tcp",
                "source": "any",
                "destination": "any",
                "destination_port": "443",
                "descr": "Allow HTTPS",
                "log": True,
            },
            {
                "id": 1,
                "tracker": 1234567891,
                "type": "block",
                "interface": ["wan"],
                "ipprotocol": "inet",
                "protocol": None,
                "source": "10.0.0.0/8",
                "destination": "any",
                "descr": "Block RFC1918 on WAN",
                "log": True,
            },
        ],
    }


@pytest.fixture()
def dhcp_leases_response():
    return {
        "status": "ok",
        "code": 200,
        "data": [
            {
                "ip": "192.168.1.100",
                "mac": "aa:bb:cc:dd:ee:01",
                "hostname": "desktop-pc",
                "if": "lan",
                "starts": "2025-01-01 00:00:00",
                "ends": "2025-01-02 00:00:00",
                "active_status": "active",
            },
            {
                "ip": "192.168.1.101",
                "mac": "aa:bb:cc:dd:ee:02",
                "hostname": "laptop",
                "if": "lan",
                "starts": "2025-01-01 12:00:00",
                "ends": "2025-01-02 12:00:00",
                "active_status": "active",
            },
        ],
    }


@pytest.fixture()
def aliases_response():
    return {
        "status": "ok",
        "code": 200,
        "data": [
            {
                "id": 0,
                "name": "blocked_hosts",
                "type": "host",
                "address": ["10.0.0.1", "10.0.0.2"],
                "descr": "Blocked hosts",
                "detail": ["Bad actor 1", "Bad actor 2"],
            },
            {
                "id": 1,
                "name": "web_ports",
                "type": "port",
                "address": ["80", "443", "8080"],
                "descr": "Web ports",
                "detail": ["HTTP", "HTTPS", "Alt HTTP"],
            },
        ],
    }


@pytest.fixture()
def services_response():
    return {
        "status": "ok",
        "code": 200,
        "data": [
            {"name": "dhcpd", "description": "DHCP Server", "status": "running"},
            {"name": "unbound", "description": "DNS Resolver", "status": "running"},
            {"name": "ntpd", "description": "NTP Daemon", "status": "stopped"},
        ],
    }


@pytest.fixture()
def firewall_logs_response():
    """Matches the real pfSense REST API v2 FirewallLog model which only has a 'text' field."""
    return {
        "status": "ok",
        "code": 200,
        "data": [
            {"text": "Jan 15 10:00:00 pfSense filterlog[12345]: 5,,,1000000103,wan,match,block,in,4,0x0,,128,12345,0,none,6,tcp,60,203.0.113.5,192.168.1.1,54321,22,0,S,"},
            {"text": "Jan 15 10:01:00 pfSense filterlog[12345]: 5,,,1000000104,lan,match,pass,in,4,0x0,,64,12346,0,none,17,udp,41,192.168.1.100,8.8.8.8,51234,53,21,"},
        ],
    }


@pytest.fixture()
def nat_forwards_response():
    return {
        "status": "ok",
        "code": 200,
        "data": [
            {
                "id": 0,
                "interface": ["wan"],
                "protocol": "tcp",
                "destination": "wanip",
                "destination_port": "8080",
                "target": "192.168.1.50",
                "local_port": "80",
                "descr": "Web server",
                "associated_rule_id": "new",
            },
        ],
    }


@pytest.fixture()
def dhcp_static_mappings_response():
    return {
        "status": "ok",
        "code": 200,
        "data": [
            {
                "id": 0,
                "mac": "aa:bb:cc:dd:ee:01",
                "ipaddr": "192.168.1.200",
                "hostname": "server1",
                "descr": "Web server reservation",
                "parent_id": "lan",
            },
            {
                "id": 1,
                "mac": "aa:bb:cc:dd:ee:02",
                "ipaddr": "192.168.1.201",
                "hostname": "server2",
                "descr": "DB server reservation",
                "parent_id": "lan",
            },
        ],
    }


@pytest.fixture()
def service_control_response():
    return {
        "status": "ok",
        "code": 200,
        "data": {"service": "dhcpd", "action": "restart"},
    }
