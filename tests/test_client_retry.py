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
