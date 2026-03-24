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

# Import tool modules — each registers tools via @mcp.tool() on import
from .tools import (  # noqa: F401
    aliases,
    certificates,
    dhcp,
    diagnostics,
    dns_resolver,
    firewall,
    firewall_schedules,
    firewall_states,
    interfaces,
    logs,
    nat,
    nat_onetoone,
    nat_outbound,
    routing,
    services,
    system,
    system_settings,
    traffic_shaper,
    users,
    utility,
    virtual_ips,
    vpn_ipsec,
    vpn_openvpn,
    vpn_wireguard,
)


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
        sys.exit(1)

    if args.transport == "stdio":
        logger.info("Starting MCP server in stdio mode...")
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        import uvicorn

        from .middleware import BearerAuthMiddleware

        app = mcp.http_app()

        # Require bearer auth for HTTP transport — fail closed
        api_key = os.getenv("MCP_API_KEY")
        if not api_key:
            logger.error(
                "MCP_API_KEY must be set for streamable-http transport. "
                "Set MCP_API_KEY or use --transport stdio."
            )
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
