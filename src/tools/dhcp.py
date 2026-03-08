"""DHCP tools for pfSense MCP server."""

from datetime import datetime
from typing import Dict, Optional

from ..helpers import create_default_sort, create_pagination
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp


async def _lookup_mapping_parent_id(client, mapping_id: int) -> str:
    """Look up a DHCP static mapping's parent_id (interface) by its ID.

    The pfSense API requires parent_id for PATCH/DELETE on child models.
    """
    result = await client.get_dhcp_static_mappings(
        filters=[QueryFilter("id", str(mapping_id))]
    )
    mappings = result.get("data", [])
    for m in mappings:
        if m.get("id") == mapping_id:
            return m["parent_id"]
    raise ValueError(f"DHCP static mapping with ID {mapping_id} not found")


@mcp.tool()
async def search_dhcp_leases(
    search_term: Optional[str] = None,
    interface: Optional[str] = None,
    mac_address: Optional[str] = None,
    hostname: Optional[str] = None,
    state: str = "active",
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "starts"
) -> Dict:
    """Search DHCP leases with advanced filtering

    Args:
        search_term: General search term for hostname or IP
        interface: Filter by interface
        mac_address: Filter by specific MAC address
        hostname: Filter by hostname (supports partial matching)
        state: Filter by lease state (active, expired, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (starts, ends, hostname, ip, mac)
    """
    client = get_api_client()
    try:
        filters = []

        if search_term:
            filters.append(QueryFilter("hostname", search_term, "contains"))

        if interface:
            # DHCP uses 'if' field, not 'interface'
            filters.append(QueryFilter("if", interface, "contains"))

        if mac_address:
            filters.append(QueryFilter("mac", mac_address))

        if hostname:
            filters.append(QueryFilter("hostname", hostname, "contains"))

        if state:
            # DHCP uses 'active_status' field, not 'state'
            filters.append(QueryFilter("active_status", state))

        pagination = create_pagination(page, page_size)
        sort = create_default_sort(sort_by, descending=True)

        leases = await client.get_dhcp_leases(
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "interface": interface,
                "mac_address": mac_address,
                "hostname": hostname,
                "state": state
            },
            "count": len(leases.get("data", [])),
            "leases": leases.get("data", []),
            "links": client.extract_links(leases),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search DHCP leases: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def search_dhcp_static_mappings(
    interface: Optional[str] = None,
    mac_address: Optional[str] = None,
    hostname: Optional[str] = None,
    ip_address: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "mac"
) -> Dict:
    """Search DHCP static mappings (reservations) with filtering

    Args:
        interface: Filter by interface (lan, opt1, etc.)
        mac_address: Filter by MAC address
        hostname: Filter by hostname (partial match)
        ip_address: Filter by IP address
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (mac, ipaddr, hostname)
    """
    client = get_api_client()
    try:
        filters = []

        if interface:
            filters.append(QueryFilter("parent_id", interface))

        if mac_address:
            filters.append(QueryFilter("mac", mac_address))

        if hostname:
            filters.append(QueryFilter("hostname", hostname, "contains"))

        if ip_address:
            filters.append(QueryFilter("ipaddr", ip_address))

        pagination = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.get_dhcp_static_mappings(
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "interface": interface,
                "mac_address": mac_address,
                "hostname": hostname,
                "ip_address": ip_address,
            },
            "count": len(result.get("data", [])),
            "static_mappings": result.get("data", []),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        # 404 typically means DHCP is not enabled on the requested interface
        if "404" in str(e) and interface:
            return {
                "success": True,
                "page": page,
                "page_size": page_size,
                "filters_applied": {"interface": interface},
                "count": 0,
                "static_mappings": [],
                "message": f"No DHCP static mappings found. DHCP may not be enabled on interface '{interface}'.",
                "timestamp": datetime.utcnow().isoformat()
            }
        logger.error(f"Failed to search DHCP static mappings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def create_dhcp_static_mapping(
    interface: str,
    mac_address: str,
    ip_address: str,
    hostname: Optional[str] = None,
    description: Optional[str] = None,
    domain: Optional[str] = None,
    gateway: Optional[str] = None,
    dns_server: Optional[str] = None,
    apply_immediately: bool = True
) -> Dict:
    """Create a DHCP static mapping (reservation)

    Args:
        interface: Interface/DHCP pool (e.g., "lan")
        mac_address: MAC address to reserve for
        ip_address: IP address to assign
        hostname: Optional hostname
        description: Optional description
        domain: Optional domain name
        gateway: Optional gateway override
        dns_server: Optional DNS server override
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        mapping_data = {
            "parent_id": interface,
            "mac": mac_address,
            "ipaddr": ip_address,
        }

        if hostname:
            mapping_data["hostname"] = hostname
        if description:
            mapping_data["descr"] = description
        if domain:
            mapping_data["domain"] = domain
        if gateway:
            mapping_data["gateway"] = gateway
        if dns_server:
            mapping_data["dnsserver"] = dns_server

        control = ControlParameters(apply=apply_immediately)
        result = await client.create_dhcp_static_mapping(mapping_data, control)

        return {
            "success": True,
            "message": f"DHCP static mapping created: {mac_address} -> {ip_address}",
            "static_mapping": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create DHCP static mapping: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_dhcp_static_mapping(
    mapping_id: int,
    mac_address: Optional[str] = None,
    ip_address: Optional[str] = None,
    hostname: Optional[str] = None,
    description: Optional[str] = None,
    interface: Optional[str] = None,
    apply_immediately: bool = True
) -> Dict:
    """Update an existing DHCP static mapping by ID

    Args:
        mapping_id: Static mapping ID
        mac_address: New MAC address
        ip_address: New IP address
        hostname: New hostname
        description: New description
        interface: New interface/DHCP pool
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "mac_address": "mac",
            "ip_address": "ipaddr",
            "hostname": "hostname",
            "description": "descr",
            "interface": "parent_id",
        }

        params = {
            "mac_address": mac_address,
            "ip_address": ip_address,
            "hostname": hostname,
            "description": description,
            "interface": interface,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        # pfSense API requires parent_id for child model operations
        if "parent_id" not in updates:
            updates["parent_id"] = await _lookup_mapping_parent_id(client, mapping_id)

        control = ControlParameters(apply=apply_immediately)
        result = await client.update_dhcp_static_mapping(mapping_id, updates, control)

        return {
            "success": True,
            "message": f"DHCP static mapping {mapping_id} updated",
            "mapping_id": mapping_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update DHCP static mapping: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_dhcp_static_mapping(
    mapping_id: int,
    interface: Optional[str] = None,
    apply_immediately: bool = True
) -> Dict:
    """Delete a DHCP static mapping by ID

    Args:
        mapping_id: Static mapping ID
        interface: Interface/DHCP pool the mapping belongs to (e.g., "lan"). Auto-detected if not provided.
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        # pfSense API requires parent_id for child model operations
        if not interface:
            interface = await _lookup_mapping_parent_id(client, mapping_id)

        result = await client.delete_dhcp_static_mapping(mapping_id, interface, apply_immediately)

        return {
            "success": True,
            "message": f"DHCP static mapping {mapping_id} deleted",
            "mapping_id": mapping_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to delete DHCP static mapping: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_dhcp_server_config(
    interface: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict:
    """Get DHCP server configuration including pool ranges, lease times, etc.

    Args:
        interface: Filter by interface (lan, opt1, etc.). Returns all if omitted.
        page: Page number for pagination
        page_size: Number of results per page
    """
    client = get_api_client()
    try:
        filters = []
        if interface:
            filters.append(QueryFilter("id", interface))

        pagination = create_pagination(page, page_size)

        result = await client.get_dhcp_servers(
            filters=filters if filters else None,
            pagination=pagination
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "interface_filter": interface,
            "count": len(result.get("data", [])),
            "dhcp_servers": result.get("data", []),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get DHCP server config: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_dhcp_server_config(
    server_id: int,
    range_from: Optional[str] = None,
    range_to: Optional[str] = None,
    gateway: Optional[str] = None,
    domain: Optional[str] = None,
    dns_server: Optional[str] = None,
    default_lease_time: Optional[int] = None,
    max_lease_time: Optional[int] = None,
    enable: Optional[bool] = None,
    apply_immediately: bool = True
) -> Dict:
    """Update DHCP server configuration (pool range, lease times, etc.)

    Args:
        server_id: DHCP server ID (from get_dhcp_server_config)
        range_from: Pool start IP address
        range_to: Pool end IP address
        gateway: Gateway IP override
        domain: Domain name
        dns_server: DNS server override
        default_lease_time: Default lease time in seconds
        max_lease_time: Maximum lease time in seconds
        enable: Enable or disable the DHCP server
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "range_from": "range_from",
            "range_to": "range_to",
            "gateway": "gateway",
            "domain": "domain",
            "dns_server": "dnsserver",
            "default_lease_time": "defaultleasetime",
            "max_lease_time": "maxleasetime",
            "enable": "enable",
        }

        params = {
            "range_from": range_from,
            "range_to": range_to,
            "gateway": gateway,
            "domain": domain,
            "dns_server": dns_server,
            "default_lease_time": default_lease_time,
            "max_lease_time": max_lease_time,
            "enable": enable,
        }

        updates = {"id": server_id}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if len(updates) <= 1:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.update_dhcp_server(updates, control)

        return {
            "success": True,
            "message": f"DHCP server {server_id} updated",
            "server_id": server_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update DHCP server config: {e}")
        return {"success": False, "error": str(e)}
