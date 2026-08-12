"""Transient-failure retry/backoff in the API client.

Policy: retry connection errors and 429/503 for any method; additionally retry
read-timeouts and 502/504 for idempotent GETs only; never retry when a
per-request read timeout is set (fast-fail log endpoints).
"""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.client import EnhancedPfSenseAPIClient
from src.models import AuthMethod, PfSenseVersion


def _client():
    return EnhancedPfSenseAPIClient(
        host="https://192.0.2.1", auth_method=AuthMethod.API_KEY, api_key="k",
        verify_ssl=False, version=PfSenseVersion.CE_2_8_1,
    )


def _resp(status, headers=None):
    req = httpx.Request("GET", "https://192.0.2.1/api/v2/x")
    return httpx.Response(status, json={"data": {}}, headers=headers or {}, request=req)


def test_transport_error_preserves_request_context():
    c = _client()
    request = httpx.Request("GET", "https://192.0.2.1/api/v2/status/system")
    error = httpx.ConnectError("boom", request=request)

    described = c._describe_transport_error(error, attempts=2)

    assert isinstance(described, httpx.ConnectError)
    assert described.request is request
    assert "3 attempt(s)" in str(described)


def test_transport_error_without_request_still_rebuilds():
    c = _client()
    error = httpx.ConnectError("boom")

    described = c._describe_transport_error(error, attempts=0)

    assert isinstance(described, httpx.ConnectError)
    assert "1 attempt(s)" in str(described)


def test_transport_error_falls_back_for_legacy_constructor():
    class LegacyTransportError(httpx.TransportError):
        def __init__(self, message):
            super().__init__(message)

    c = _client()
    request = httpx.Request("GET", "https://192.0.2.1/api/v2/status/system")
    error = LegacyTransportError("boom")
    error._request = request

    described = c._describe_transport_error(error, attempts=0)

    assert isinstance(described, LegacyTransportError)
    assert "1 attempt(s)" in str(described)


@pytest.fixture
def no_sleep():
    with patch("asyncio.sleep", new_callable=AsyncMock) as s:
        yield s


async def test_get_retries_connection_error_then_succeeds(no_sleep):
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.side_effect = [httpx.ConnectError("boom"), httpx.ConnectError("boom"), _resp(200)]
        result = await c._make_request("GET", "/firewall/rule")
    assert result == {"data": {}}
    assert send.await_count == 3
    assert no_sleep.await_count == 2


async def test_post_retries_503_then_succeeds(no_sleep):
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.side_effect = [_resp(503), _resp(200)]
        result = await c._make_request("POST", "/firewall/rule", data={"x": 1})
    assert result == {"data": {}}
    assert send.await_count == 2


async def test_post_not_retried_on_read_timeout(no_sleep):
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.side_effect = httpx.ReadTimeout("t")
        with pytest.raises(httpx.ReadTimeout):
            await c._make_request("POST", "/firewall/rule", data={"x": 1})
    assert send.await_count == 1  # a write is never silently re-applied


async def test_get_retries_502(no_sleep):
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.side_effect = [_resp(502), _resp(200)]
        await c._make_request("GET", "/status/system")
    assert send.await_count == 2


async def test_post_not_retried_on_502(no_sleep):
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        # 502 on a POST is ambiguous → surfaced, not retried. The 4xx/5xx path
        # raises the standard API error.
        send.side_effect = [_resp(502)]
        with pytest.raises(Exception):
            await c._make_request("POST", "/firewall/rule", data={"x": 1})
    assert send.await_count == 1


async def test_retry_after_header_is_honored(no_sleep):
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.side_effect = [_resp(429, headers={"Retry-After": "2"}), _resp(200)]
        await c._make_request("GET", "/firewall/rule")
    no_sleep.assert_awaited_with(2.0)


async def test_no_retry_when_read_timeout_override_set(no_sleep):
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.side_effect = httpx.ConnectError("boom")
        with pytest.raises(httpx.ConnectError):
            await c._make_request("GET", "/status/logs", timeout=5)
    assert send.await_count == 1  # log endpoints fail fast


async def test_retries_are_bounded(no_sleep):
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.side_effect = httpx.ConnectError("boom")
        with pytest.raises(httpx.ConnectError):
            await c._make_request("GET", "/firewall/rule")
    assert send.await_count == c._MAX_RETRIES + 1  # initial + retries


async def test_default_request_uses_client_timeout_not_disabled(no_sleep):
    # Regression: passing timeout=None to httpx DISABLES timeouts entirely
    # (it is not "use the client default"). A request without a per-request
    # override must send the USE_CLIENT_DEFAULT sentinel so the client-level
    # API_TIMEOUT stays in force; None here means every call can hang until
    # the OS abandons the TCP connect (~minutes against a black-holed host).
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.return_value = _resp(200)
        await c._make_request("GET", "/firewall/rule")
    assert send.await_args.args[4] is httpx.USE_CLIENT_DEFAULT


async def test_log_endpoint_read_timeout_override_is_scoped(no_sleep):
    # The fast-fail override shortens only the read phase; connect/write/pool
    # keep the client-level timeout.
    c = _client()
    with patch.object(c, "_send", new_callable=AsyncMock) as send:
        send.return_value = _resp(200)
        await c._make_request("GET", "/status/logs", timeout=5)
    t = send.await_args.args[4]
    assert isinstance(t, httpx.Timeout)
    assert t.read == 5
    assert t.connect == c.timeout
