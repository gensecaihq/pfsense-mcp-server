"""Tests for the optional GCF response encoding (RESPONSE_FORMAT=gcf).

Skipped unless the optional ``gcf`` extra is installed
(``pip install 'pfsense-mcp-server[gcf]'``).
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("gcf.fastmcp")

from fastmcp.tools.tool import ToolResult  # noqa: E402
from gcf import decode_generic  # noqa: E402
from gcf.fastmcp import GcfResponseMiddleware  # noqa: E402
from mcp.types import TextContent  # noqa: E402


def _run(middleware, result):
    async def call_next(_context):
        return result

    return asyncio.run(middleware.on_call_tool(SimpleNamespace(), call_next))


def _result(payload):
    return ToolResult(
        content=[TextContent(type="text", text=json.dumps(payload))],
        structured_content=payload,
    )


def _firewall_rules(n):
    """A search_firewall_rules-shaped result: a record array under ``rules``."""
    return {
        "success": True,
        "count": n,
        "rules": [
            {
                "id": i,
                "type": "pass" if i % 3 else "block",
                "interface": "wan",
                "ipprotocol": "inet",
                "protocol": "tcp",
                "source": "any",
                "destination": "192.168.1.0/24",
                "descr": f"allow rule {i}",
                "disabled": False,
            }
            for i in range(n)
        ],
    }


def test_firewall_rules_encode_smaller_and_lossless():
    payload = _firewall_rules(15)
    out = _run(GcfResponseMiddleware(enabled=True), _result(payload))

    wire = out.content[0].text
    assert wire.startswith("GCF profile=generic")
    assert len(wire) < len(json.dumps(payload))  # never-grow held
    assert decode_generic(wire) == payload  # lossless: no record dropped or altered
    assert out.structured_content == payload  # preserved for non-model clients


def test_small_result_keeps_json():
    # An empty result set: GCF's header overhead exceeds the JSON, so the
    # never-grow guard keeps the JSON rather than emit a larger wire.
    payload = {"success": True, "count": 0, "rules": []}
    out = _run(GcfResponseMiddleware(enabled=True), _result(payload))

    assert out.content[0].text == json.dumps(payload)
    assert not out.content[0].text.startswith("GCF ")


def test_disabled_by_default(monkeypatch):
    # Without RESPONSE_FORMAT=gcf the middleware is a no-op.
    monkeypatch.delenv("RESPONSE_FORMAT", raising=False)
    payload = _firewall_rules(15)
    out = _run(GcfResponseMiddleware(), _result(payload))

    assert out.content[0].text == json.dumps(payload)
