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

# Re-export all tool FunctionTool objects so ``_main.system_status`` still works in tests
system_status = system.system_status
search_interfaces = system.search_interfaces
find_interfaces_by_status = system.find_interfaces_by_status

search_firewall_rules = firewall.search_firewall_rules
find_blocked_rules = firewall.find_blocked_rules
create_firewall_rule_advanced = firewall.create_firewall_rule_advanced
move_firewall_rule = firewall.move_firewall_rule
update_firewall_rule = firewall.update_firewall_rule
delete_firewall_rule = firewall.delete_firewall_rule
bulk_block_ips = firewall.bulk_block_ips

search_aliases = aliases.search_aliases
manage_alias_addresses = aliases.manage_alias_addresses
create_alias = aliases.create_alias
update_alias = aliases.update_alias
delete_alias = aliases.delete_alias

search_nat_port_forwards = nat.search_nat_port_forwards
create_nat_port_forward = nat.create_nat_port_forward
delete_nat_port_forward = nat.delete_nat_port_forward
update_nat_port_forward = nat.update_nat_port_forward

get_firewall_log = logs.get_firewall_log
analyze_blocked_traffic = logs.analyze_blocked_traffic
search_logs_by_ip = logs.search_logs_by_ip

search_services = services.search_services
control_service = services.control_service

search_dhcp_leases = dhcp.search_dhcp_leases
search_dhcp_static_mappings = dhcp.search_dhcp_static_mappings
create_dhcp_static_mapping = dhcp.create_dhcp_static_mapping
update_dhcp_static_mapping = dhcp.update_dhcp_static_mapping
delete_dhcp_static_mapping = dhcp.delete_dhcp_static_mapping

follow_api_link = utility.follow_api_link
enable_hateoas = utility.enable_hateoas
disable_hateoas = utility.disable_hateoas
refresh_object_ids = utility.refresh_object_ids
find_object_by_field = utility.find_object_by_field
get_api_capabilities = utility.get_api_capabilities
test_enhanced_connection = utility.test_enhanced_connection


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
