#!/usr/bin/env python3
"""
Enhanced pfSense MCP Server with Advanced API Features
Implements: Object IDs, Queries/Filters, HATEOAS, Control Parameters
Compatible with pfSense REST API v2 (jaredhendrickson13/pfsense-api)
"""

import asyncio
import os
import sys

from .server import VERSION, get_api_client, logger, mcp, reset_api_client

# Read-only mode: only register read-level tools (MCP security best practice: least privilege)
_READ_ONLY_MODE = os.getenv("MCP_READ_ONLY", "false").lower() == "true"

# Import tool modules — each registers tools via @mcp.tool() on import
from .tools import (  # noqa: F401, E402
    aliases,
    certificates,
    dhcp,
    dhcp_advanced,
    diagnostics,
    dns_forwarder,
    dns_resolver,
    firewall,
    firewall_schedules,
    firewall_states,
    interfaces,
    logs,
    misc_services,
    nat,
    nat_onetoone,
    nat_outbound,
    pkg_acme,
    pkg_bind,
    pkg_freeradius,
    pkg_haproxy,
    routing,
    services,
    system,
    system_advanced,
    system_settings,
    traffic_shaper,
    troubleshoot,
    users,
    utility,
    virtual_ips,
    vpn_advanced,
    vpn_ipsec,
    vpn_openvpn,
    vpn_wireguard,
)


def apply_read_only_filter() -> int:
    """In read-only mode, remove every non-read tool. Returns the count removed.

    Called from ``main()`` — deliberately NOT at import time. Doing this at
    module scope means running ``asyncio.run()`` while ``src.main`` is still
    being imported; on Python 3.11 (coarser import lock than 3.12+) any lazy
    import triggered by that coroutine can deadlock. Running it from ``main()``,
    after all imports complete, avoids that entirely.

    Uses FastMCP's public local-provider API (``list_tools`` / ``remove_tool``);
    the pre-3.0 code reached into ``mcp._tool_manager._tools``, which FastMCP 3
    removed. ``tests/test_read_only_mode.py`` exercises this so neither the crash
    nor the import-time hang can recur.
    """
    if not _READ_ONLY_MODE:
        return 0

    from .guardrails import RiskLevel, classify_risk

    provider = mcp.local_provider
    names = [t.name for t in asyncio.run(provider.list_tools())]
    removed = 0
    for name in names:
        if classify_risk(name) != RiskLevel.READ:
            provider.remove_tool(name)
            removed += 1
    logger.info(
        "READ-ONLY MODE: removed %d non-read tools; %d read-only tools available.",
        removed, len(names) - removed,
    )
    return removed


_MIN_API_KEY_LEN = 16
_PLACEHOLDER_KEYS = {"changeme", "change-me", "your-token-here", "secret", "token"}


def mcp_api_key_error(api_key):
    """Return an error string if MCP_API_KEY is unusable, else None.

    Rejects an unset key, the documented ``CHANGE-ME`` placeholder, and tokens
    too short to be a real secret — so an HTTP deployment can't boot with a
    publicly-known or trivially-guessable bearer token. Supports the
    comma-separated multi-key form; every key must be valid.
    """
    if not api_key or not api_key.strip():
        return (
            "MCP_API_KEY must be set for streamable-http transport. "
            "Set MCP_API_KEY or use --transport stdio."
        )
    for key in (k.strip() for k in api_key.split(",") if k.strip()):
        low = key.lower()
        if low in _PLACEHOLDER_KEYS or low.startswith("change-me") or low.startswith("changeme"):
            return (
                "MCP_API_KEY is set to a placeholder value. Generate a real token, "
                "e.g. `python -c \"import secrets; print(secrets.token_urlsafe(32))\"`."
            )
        if len(key) < _MIN_API_KEY_LEN:
            return (
                f"MCP_API_KEY token is too short ({len(key)} chars); "
                f"use at least {_MIN_API_KEY_LEN} characters of entropy."
            )
    return None


# Main execution
def main():
    """Main entry point for the Enhanced pfSense MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="pfSense MCP Server")
    parser.add_argument(
        "-t", "--transport",
        choices=["stdio", "streamable-http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport mode (default: stdio)"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host to bind to in HTTP mode (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "3000")),
        help="Port to bind to in HTTP mode (default: 3000)"
    )
    args = parser.parse_args()

    logger.info(f"Starting Enhanced pfSense MCP Server v{VERSION}")
    logger.info(f"Connecting to pfSense at: {os.getenv('PFSENSE_URL')}")
    logger.info(f"Auth Method: {os.getenv('AUTH_METHOD', 'api_key')}")
    logger.info(f"Transport: {args.transport}")

    # Security warnings per MCP spec best practices
    if os.getenv("VERIFY_SSL", "true").lower() == "false":
        logger.warning(
            "SECURITY: SSL verification is DISABLED (VERIFY_SSL=false). "
            "This is acceptable for self-signed certs in labs but NOT recommended for production."
        )
    if args.transport == "streamable-http" and args.host != "127.0.0.1" and args.host != "localhost":
        logger.warning(
            "SECURITY: HTTP transport is binding to %s (not localhost). "
            "Ensure TLS is terminated by a reverse proxy (nginx, Caddy) in production.",
            args.host,
        )

    # Apply the read-only tool filter (no-op unless MCP_READ_ONLY=true) before
    # the server begins serving.
    apply_read_only_filter()

    # Test connection before starting server
    async def test_conn():
        client = get_api_client()
        try:
            logger.info("Testing connection to pfSense API...")
            result = await client.test_connection()
            if result["connected"]:
                logger.info("Successfully connected to pfSense API")
                return True
            else:
                logger.error("Failed to connect to pfSense API: %s", result.get("error", "unknown error"))
                return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            # Close the client and clear the singleton so the MCP server
            # event loop gets a completely fresh instance
            await client.close()
            reset_api_client()

    connected = asyncio.run(test_conn())
    if not connected:
        # A transient blip at launch (slow TLS handshake, momentary network
        # hiccup) shouldn't kill the server before it ever opens its stdio
        # channel — MCP clients would only see an opaque connection/protocol
        # error. Start anyway; each tool surfaces connectivity errors when
        # actually invoked. See PR #14.
        logger.warning(
            "Preflight connectivity check failed; starting MCP server anyway. "
            "Tools will surface errors individually if pfSense is actually unreachable."
        )

    if args.transport == "stdio":
        logger.info("Starting MCP server in stdio mode...")
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        import uvicorn

        from .middleware import BearerAuthMiddleware

        app = mcp.http_app()

        # Require a real bearer token for HTTP transport — fail closed on unset,
        # placeholder, or weak keys.
        api_key = os.getenv("MCP_API_KEY")
        key_error = mcp_api_key_error(api_key)
        if key_error:
            logger.error(key_error)
            sys.exit(1)
        # Parse allowed origins from env (comma-separated) or use defaults
        allowed_origins_str = os.getenv("MCP_ALLOWED_ORIGINS", "")
        allowed_origins = None
        if allowed_origins_str.strip():
            allowed_origins = {o.strip().rstrip("/").lower() for o in allowed_origins_str.split(",")}
            logger.info("Allowed origins: %s", allowed_origins)

        app = BearerAuthMiddleware(app, api_key, allowed_origins=allowed_origins)
        logger.info("Bearer token auth and Origin validation enabled")

        logger.info(f"Starting MCP server on http://{args.host}:{args.port}/mcp")
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
