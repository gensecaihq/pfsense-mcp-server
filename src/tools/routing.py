"""Routing tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import create_default_sort, create_pagination, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Gateways
# ---------------------------------------------------------------------------


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_gateways(
    search_term: Optional[str] = None,
    interface: Optional[str] = None,
    protocol: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search routing gateways with filtering and pagination

    Args:
        search_term: General search across gateway name/description (client-side filter)
        interface: Filter by interface (wan, lan, opt1, etc.)
        protocol: Filter by IP protocol (inet for IPv4, inet6 for IPv6)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, interface, gateway, monitor, weight, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if interface:
            filters.append(QueryFilter("interface", interface))

        if protocol:
            if protocol not in ("inet", "inet6"):
                return {"success": False, "error": "protocol must be 'inet' (IPv4) or 'inet6' (IPv6)"}
            filters.append(QueryFilter("ipprotocol", protocol))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/routing/gateways",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        gateways = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            gateways = [
                gw for gw in gateways
                if term_lower in gw.get("name", "").lower()
                or term_lower in gw.get("descr", "").lower()
                or term_lower in gw.get("gateway", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "interface": interface,
                "protocol": protocol,
            },
            "count": len(gateways),
            "gateways": gateways,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search gateways: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_gateway(
    interface: str,
    name: str,
    gateway: str,
    ipprotocol: str = "inet",
    monitor: Optional[str] = None,
    weight: Optional[int] = None,
    descr: Optional[str] = None,
    disabled: bool = False,
    apply_immediately: bool = True,
) -> Dict:
    """Create a routing gateway

    Args:
        interface: Interface for the gateway (wan, lan, opt1, etc.)
        name: Gateway name (alphanumeric and underscores only)
        gateway: Gateway IP address
        ipprotocol: IP protocol version (inet for IPv4, inet6 for IPv6)
        monitor: Monitor IP address (defaults to gateway IP if omitted)
        weight: Gateway weight for load balancing (1-30)
        descr: Optional description
        disabled: Whether the gateway starts disabled
        apply_immediately: Whether to apply changes immediately
    """
    if ipprotocol not in ("inet", "inet6"):
        return {"success": False, "error": "ipprotocol must be 'inet' (IPv4) or 'inet6' (IPv6)"}

    if weight is not None and (weight < 1 or weight > 30):
        return {"success": False, "error": "weight must be between 1 and 30"}

    client = get_api_client()
    try:
        gw_data: Dict[str, Union[str, int, bool]] = {
            "interface": interface,
            "name": name,
            "gateway": gateway,
            "ipprotocol": ipprotocol,
            "disabled": disabled,
        }

        if monitor:
            gw_data["monitor"] = monitor
        if weight is not None:
            gw_data["weight"] = weight
        if descr:
            gw_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/routing/gateway", gw_data, control)

        return {
            "success": True,
            "message": f"Gateway '{name}' created on {interface} -> {gateway}",
            "gateway": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create gateway: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_gateway(
    gateway_id: int,
    interface: Optional[str] = None,
    name: Optional[str] = None,
    gateway: Optional[str] = None,
    ipprotocol: Optional[str] = None,
    monitor: Optional[str] = None,
    weight: Optional[int] = None,
    descr: Optional[str] = None,
    disabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing routing gateway by ID

    Args:
        gateway_id: Gateway ID (from search_gateways)
        interface: Interface for the gateway
        name: Gateway name
        gateway: Gateway IP address
        ipprotocol: IP protocol version (inet or inet6)
        monitor: Monitor IP address
        weight: Gateway weight for load balancing (1-30)
        descr: Description
        disabled: Whether the gateway is disabled
        apply_immediately: Whether to apply changes immediately
    """
    if ipprotocol is not None and ipprotocol not in ("inet", "inet6"):
        return {"success": False, "error": "ipprotocol must be 'inet' (IPv4) or 'inet6' (IPv6)"}

    if weight is not None and (weight < 1 or weight > 30):
        return {"success": False, "error": "weight must be between 1 and 30"}

    client = get_api_client()
    try:
        field_map = {
            "interface": "interface",
            "name": "name",
            "gateway": "gateway",
            "ipprotocol": "ipprotocol",
            "monitor": "monitor",
            "weight": "weight",
            "descr": "descr",
            "disabled": "disabled",
        }

        params = {
            "interface": interface,
            "name": name,
            "gateway": gateway,
            "ipprotocol": ipprotocol,
            "monitor": monitor,
            "weight": weight,
            "descr": descr,
            "disabled": disabled,
        }

        updates: Dict[str, Union[str, int, bool]] = {}
        for param_name, value in params.items():
            if value is not None:
                api_field = field_map[param_name]
                if api_field == "descr" and isinstance(value, str):
                    updates[api_field] = sanitize_description(value)
                else:
                    updates[api_field] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/routing/gateway", gateway_id, updates, control)

        return {
            "success": True,
            "message": f"Gateway {gateway_id} updated",
            "gateway_id": gateway_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update gateway: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_gateway(
    gateway_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a routing gateway by ID. WARNING: This is irreversible.

    Args:
        gateway_id: Gateway ID (from search_gateways)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/routing/gateway", gateway_id, control)

        return {
            "success": True,
            "message": f"Gateway {gateway_id} deleted",
            "gateway_id": gateway_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query gateways before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete gateway: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Default Gateway
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_default_gateway() -> Dict:
    """Get the current default gateway settings (IPv4 and IPv6)"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/routing/gateway/default")

        return {
            "success": True,
            "default_gateway": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get default gateway: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_default_gateway(
    defaultgw4: Optional[str] = None,
    defaultgw6: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the default gateway settings

    Args:
        defaultgw4: Default IPv4 gateway name (must match an existing gateway name)
        defaultgw6: Default IPv6 gateway name (must match an existing gateway name)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict[str, str] = {}

        if defaultgw4 is not None:
            updates["defaultgw4"] = defaultgw4
        if defaultgw6 is not None:
            updates["defaultgw6"] = defaultgw6

        if not updates:
            return {"success": False, "error": "No fields to update - provide defaultgw4 and/or defaultgw6"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/routing/gateway/default", updates, control)

        return {
            "success": True,
            "message": "Default gateway updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update default gateway: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Gateway Groups
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_gateway_groups(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search gateway groups with filtering and pagination

    Args:
        search_term: Search in group name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, trigger, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/routing/gateway/groups",
            sort=sort,
            pagination=pagination,
        )

        groups = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            groups = [
                g for g in groups
                if term_lower in g.get("name", "").lower()
                or term_lower in g.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(groups),
            "gateway_groups": groups,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search gateway groups: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_gateway_group(
    name: str,
    trigger: str,
    priorities: List[Dict],
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a gateway group for multi-WAN failover or load balancing

    Args:
        name: Gateway group name (alphanumeric and underscores only)
        trigger: Failover trigger level (e.g., "down", "downloss", "downlatency", "downlosslatency")
        priorities: Array of gateway priority entries, e.g. [{"gateway": "WAN_GW", "tier": 1, "virtual_ip": ""}]
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        group_data: Dict[str, Union[str, List, bool]] = {
            "name": name,
            "trigger": trigger,
            "priorities": priorities,
        }

        if descr:
            group_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/routing/gateway/group", group_data, control)

        return {
            "success": True,
            "message": f"Gateway group '{name}' created",
            "gateway_group": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create gateway group: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_gateway_group(
    group_id: int,
    name: Optional[str] = None,
    trigger: Optional[str] = None,
    priorities: Optional[List[Dict]] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing gateway group by ID

    Args:
        group_id: Gateway group ID (from search_gateway_groups)
        name: Gateway group name
        trigger: Failover trigger level (down, downloss, downlatency, downlosslatency)
        priorities: Array of gateway priority entries
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict[str, Union[str, List]] = {}

        if name is not None:
            updates["name"] = name
        if trigger is not None:
            updates["trigger"] = trigger
        if priorities is not None:
            updates["priorities"] = priorities
        if descr is not None:
            updates["descr"] = sanitize_description(descr)

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/routing/gateway/group", group_id, updates, control)

        return {
            "success": True,
            "message": f"Gateway group {group_id} updated",
            "group_id": group_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update gateway group: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_gateway_group(
    group_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a gateway group by ID. WARNING: This is irreversible.

    Args:
        group_id: Gateway group ID (from search_gateway_groups)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/routing/gateway/group", group_id, control)

        return {
            "success": True,
            "message": f"Gateway group {group_id} deleted",
            "group_id": group_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query gateway groups before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete gateway group: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Static Routes
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_static_routes(
    search_term: Optional[str] = None,
    gateway: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "network",
) -> Dict:
    """Search static routes with filtering and pagination

    Args:
        search_term: Search in network/description (client-side filter)
        gateway: Filter by gateway name
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (network, gateway, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if gateway:
            filters.append(QueryFilter("gateway", gateway))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/routing/static_routes",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        routes = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            routes = [
                r for r in routes
                if term_lower in r.get("network", "").lower()
                or term_lower in r.get("descr", "").lower()
                or term_lower in r.get("gateway", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "gateway": gateway,
            },
            "count": len(routes),
            "static_routes": routes,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search static routes: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_static_route(
    network: str,
    gateway: str,
    descr: Optional[str] = None,
    disabled: bool = False,
    apply_immediately: bool = True,
) -> Dict:
    """Create a static route

    Args:
        network: Destination network in CIDR notation (e.g., "10.0.0.0/24")
        gateway: Gateway name to route through (must match an existing gateway)
        descr: Optional description
        disabled: Whether the route starts disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        route_data: Dict[str, Union[str, bool]] = {
            "network": network,
            "gateway": gateway,
            "disabled": disabled,
        }

        if descr:
            route_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/routing/static_route", route_data, control)

        return {
            "success": True,
            "message": f"Static route created: {network} via {gateway}",
            "static_route": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create static route: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_static_route(
    route_id: int,
    network: Optional[str] = None,
    gateway: Optional[str] = None,
    descr: Optional[str] = None,
    disabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing static route by ID

    Args:
        route_id: Static route ID (from search_static_routes)
        network: Destination network in CIDR notation
        gateway: Gateway name to route through
        descr: Description
        disabled: Whether the route is disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict[str, Union[str, bool]] = {}

        if network is not None:
            updates["network"] = network
        if gateway is not None:
            updates["gateway"] = gateway
        if descr is not None:
            updates["descr"] = sanitize_description(descr)
        if disabled is not None:
            updates["disabled"] = disabled

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/routing/static_route", route_id, updates, control)

        return {
            "success": True,
            "message": f"Static route {route_id} updated",
            "route_id": route_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update static route: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_static_route(
    route_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a static route by ID. WARNING: This is irreversible.

    Args:
        route_id: Static route ID (from search_static_routes)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/routing/static_route", route_id, control)

        return {
            "success": True,
            "message": f"Static route {route_id} deleted",
            "route_id": route_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query static routes before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete static route: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Apply & Status
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_routing_changes() -> Dict:
    """Apply pending routing changes (gateways, static routes, gateway groups)

    Use this after making changes with apply_immediately=False to batch-apply them.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/routing/apply")

        return {
            "success": True,
            "message": "Routing changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply routing changes: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_gateway_status() -> Dict:
    """Get real-time gateway status including latency, packet loss, and online/offline state"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/status/gateways")

        return {
            "success": True,
            "gateway_status": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get gateway status: {e}")
        return {"success": False, "error": str(e)}
