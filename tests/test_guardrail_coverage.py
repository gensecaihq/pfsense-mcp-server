"""Registration-time enforcement of guardrail coverage.

The confirm gate and rate limiter are applied per-tool via decorators, so a new
mutating tool that forgets `@guarded`/`@rate_limited` would silently ship with
no rate limiting, input sanitization, allowlist check, or audit trail. These
tests fail if any non-READ tool is undecorated, or if any HIGH/CRITICAL tool
lacks the full `@guarded` gate — turning "someone forgot a decorator" from a
silent security hole into a red test.
"""
import pytest

from src.guardrails import RiskLevel, classify_risk


async def _registered_tools():
    import src.main  # noqa: F401 — registers all tools
    from src.server import mcp

    return await mcp.local_provider.list_tools()


@pytest.mark.asyncio
async def test_every_non_read_tool_carries_a_guardrail_decorator():
    tools = await _registered_tools()
    gaps = [
        t.name
        for t in tools
        if classify_risk(t.name) != RiskLevel.READ
        and getattr(t.fn, "_guardrail", None) is None
    ]
    assert not gaps, (
        "these mutating tools have no @guarded/@rate_limited decorator "
        f"(no rate-limit / sanitization / allowlist / audit): {sorted(gaps)}"
    )


@pytest.mark.asyncio
async def test_high_and_critical_tools_use_the_full_confirm_gate():
    tools = await _registered_tools()
    weak = [
        (t.name, getattr(t.fn, "_guardrail", None))
        for t in tools
        if classify_risk(t.name) in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        and getattr(t.fn, "_guardrail", None) != "guarded"
    ]
    assert not weak, f"HIGH/CRITICAL tools must be @guarded, not merely rate_limited: {weak}"
