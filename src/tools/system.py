"""System tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_default_sort, create_pagination
from ..models import QueryFilter
from ..server import get_api_client, logger, mcp


@mcp.tool()
async def system_status() -> Dict:
    """Get current system status including CPU, memory, disk usage, and version info"""
    client = get_api_client()
    try:
        status = await client.get_system_status()

        # Extract HATEOAS links if available
        links = client.extract_links(status)

        return {
            "success": True,
            "data": status.get("data", status),
            "links": links,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def search_interfaces(
    search_term: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name"
) -> Dict:
    """Search and filter network interfaces with advanced options

    Args:
        search_term: Search in interface names/descriptions
        status_filter: Filter by status (up, down, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, status, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if search_term:
            filters.append(QueryFilter("name", search_term, "contains"))

        if status_filter:
            filters.append(QueryFilter("status", status_filter))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        interfaces = await client.get_interfaces(
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "total_results": len(interfaces.get("data") or []),
            "interfaces": interfaces.get("data") or [],
            "links": client.extract_links(interfaces),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search interfaces: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def find_interfaces_by_status(status: str) -> Dict:
    """Find interfaces by their current status

    Args:
        status: Interface status to filter by (up, down, etc.)
    """
    client = get_api_client()
    try:
        interfaces = await client.find_interfaces_by_status(status)

        return {
            "success": True,
            "status_filter": status,
            "count": len(interfaces.get("data") or []),
            "interfaces": interfaces.get("data") or [],
            "links": client.extract_links(interfaces),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to find interfaces by status: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_arp_table(
    ip_address: Optional[str] = None,
    mac_address: Optional[str] = None,
    interface: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict:
    """Get the ARP table to discover devices on the network.

    Shows IP-to-MAC address mappings for all devices that have recently
    communicated on the network, including those without static DHCP mappings.

    Args:
        ip_address: Filter by IP address (partial match)
        mac_address: Filter by MAC address (partial match)
        interface: Filter by interface (lan, opt1, etc.)
        page: Page number for pagination
        page_size: Number of results per page
    """
    client = get_api_client()
    try:
        filters: List[QueryFilter] = []

        if ip_address:
            filters.append(QueryFilter("ip_address", ip_address, "contains"))

        if mac_address:
            filters.append(QueryFilter("mac_address", mac_address, "contains"))

        if interface:
            filters.append(QueryFilter("interface", interface, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)

        result = await client.get_arp_table(
            filters=filters if filters else None,
            pagination=pagination
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "ip_address": ip_address,
                "mac_address": mac_address,
                "interface": interface,
            },
            "count": len(result.get("data") or []),
            "arp_entries": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get ARP table: {e}")
        return {"success": False, "error": str(e)}
