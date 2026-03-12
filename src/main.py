#!/usr/bin/env python3
"""
Enhanced pfSense MCP Server with Advanced API Features
Implements: Object IDs, Queries/Filters, HATEOAS, Control Parameters
Compatible with pfSense REST API v2 (jaredhendrickson13/pfsense-api)
"""

import asyncio
import os
import sys

from .server import VERSION, get_api_client, logger, mcp

# Import tool modules — each registers tools via @mcp.tool() on import
from .tools import (  # noqa: F401
    aliases,
    dhcp,
    firewall,
    logs,
    nat,
    services,
    system,
    utility,
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
        default=os.getenv("MCP_HOST", "0.0.0.0"),
        help="Host to bind to in HTTP mode (default: 0.0.0.0)"
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
            connected = await client.test_connection()
            if connected:
                logger.info("Successfully connected to pfSense API")
                return True
            else:
                logger.error("Failed to connect to pfSense API")
                logger.error("Please check your PFSENSE_URL, PFSENSE_API_KEY, and network connectivity")
                return False
        except Exception as e:
            logger.error(f"Connection error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        finally:
            # Close the client so the MCP server event loop gets a fresh one
            await client.close()
            client.reset()

    connected = asyncio.run(test_conn())
    if not connected:
        sys.exit(1)

    if args.transport == "stdio":
        logger.info("Starting MCP server in stdio mode...")
        mcp.run(transport="stdio")
    elif args.transport == "streamable-http":
        import uvicorn

        from .middleware import BearerAuthMiddleware

        # Use sse_app() for FastMCP < 2.14, http_app() for >= 2.14
        if hasattr(mcp, 'http_app'):
            app = mcp.http_app()
        else:
            app = mcp.sse_app()

        # Wrap with bearer auth if MCP_API_KEY is set
        api_key = os.getenv("MCP_API_KEY")
        if api_key:
            app = BearerAuthMiddleware(app, api_key)
            logger.info("Bearer token auth enabled (MCP_API_KEY is set)")
        else:
            logger.warning("No MCP_API_KEY set - HTTP endpoint is unauthenticated")

        logger.info(f"Starting MCP server on http://{args.host}:{args.port}/mcp")
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
