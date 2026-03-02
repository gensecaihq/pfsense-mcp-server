"""NAT port forward tools for pfSense MCP server."""

from datetime import datetime
from typing import Dict, Optional, Union

from ..helpers import create_default_sort, create_interface_filter, create_pagination
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp


@mcp.tool()
async def search_nat_port_forwards(
    interface: Optional[str] = None,
    protocol: Optional[str] = None,
    destination_port: Optional[Union[int, str]] = None,
    search_description: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "interface"
) -> Dict:
    """Search NAT port forwarding rules with filtering and pagination

    Args:
        interface: Filter by interface (wan, lan, etc.)
        protocol: Filter by protocol (tcp, udp, tcp/udp)
        destination_port: Filter by external destination port
        search_description: Search in rule descriptions
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (interface, protocol, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if interface:
            filters.append(create_interface_filter(interface))

        if protocol:
            filters.append(QueryFilter("protocol", protocol))

        if destination_port:
            filters.append(QueryFilter("destination_port", str(destination_port)))

        if search_description:
            filters.append(QueryFilter("descr", search_description, "contains"))

        pagination = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client._make_request(
            "GET", "/firewall/nat/port_forwards",
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
                "protocol": protocol,
                "destination_port": destination_port,
                "search_description": search_description
            },
            "count": len(result.get("data", [])),
            "port_forwards": result.get("data", []),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search NAT port forwards: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def create_nat_port_forward(
    interface: str,
    protocol: str,
    destination: str,
    destination_port: str,
    target: str,
    local_port: str,
    source: str = "any",
    description: Optional[str] = None,
    disabled: bool = False,
    nat_reflection: Optional[str] = None,
    create_associated_rule: bool = True,
    apply_immediately: bool = True
) -> Dict:
    """Create a NAT port forwarding rule

    Args:
        interface: Interface for the rule (typically "wan")
        protocol: Protocol (tcp, udp, tcp/udp)
        destination: External address (e.g., "wanip", "any", or specific IP/alias)
        destination_port: External port or range (e.g., "80", "8080-8090")
        target: Internal host IP address or alias to forward to
        local_port: Internal port to forward to (e.g., "80")
        source: Source address filter (default: "any")
        description: Optional rule description
        disabled: Whether the rule starts disabled
        nat_reflection: NAT reflection mode (enable, disable, purenat)
        create_associated_rule: Whether to create an associated firewall pass rule
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        forward_data = {
            "interface": [interface] if isinstance(interface, str) else interface,
            "protocol": protocol,
            "destination": destination,
            "destination_port": destination_port,
            "target": target,
            "local_port": local_port,
            "source": source,
            "disabled": disabled,
            "associated_rule_id": "new" if create_associated_rule else "",
        }

        if description:
            forward_data["descr"] = description
        else:
            forward_data["descr"] = f"Port forward via MCP at {datetime.utcnow().isoformat()}"

        if nat_reflection:
            forward_data["natreflection"] = nat_reflection

        control = ControlParameters(apply=apply_immediately)

        result = await client._make_request(
            "POST", "/firewall/nat/port_forward",
            data=forward_data, control=control
        )

        return {
            "success": True,
            "message": f"NAT port forward created: {interface} {protocol}/{destination_port} -> {target}:{local_port}",
            "port_forward": result.get("data", result),
            "applied": apply_immediately,
            "associated_rule_created": create_associated_rule,
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create NAT port forward: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def delete_nat_port_forward(
    port_forward_id: int,
    apply_immediately: bool = True
) -> Dict:
    """Delete a NAT port forwarding rule by ID

    Args:
        port_forward_id: Port forward rule ID (array index from search_nat_port_forwards)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)

        result = await client._make_request(
            "DELETE", "/firewall/nat/port_forward",
            data={"id": port_forward_id}, control=control
        )

        return {
            "success": True,
            "message": f"NAT port forward {port_forward_id} deleted",
            "port_forward_id": port_forward_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to delete NAT port forward: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def update_nat_port_forward(
    port_forward_id: int,
    interface: Optional[str] = None,
    protocol: Optional[str] = None,
    destination: Optional[str] = None,
    destination_port: Optional[str] = None,
    target: Optional[str] = None,
    local_port: Optional[str] = None,
    source: Optional[str] = None,
    description: Optional[str] = None,
    disabled: Optional[bool] = None,
    nat_reflection: Optional[str] = None,
    apply_immediately: bool = True
) -> Dict:
    """Update an existing NAT port forwarding rule by ID

    Args:
        port_forward_id: Port forward rule ID (array index from search_nat_port_forwards)
        interface: Interface for the rule (wan, lan, etc.)
        protocol: Protocol (tcp, udp, tcp/udp)
        destination: External address (e.g., "wanip", "any", or specific IP/alias)
        destination_port: External port or range
        target: Internal host IP address or alias
        local_port: Internal port to forward to
        source: Source address filter
        description: Rule description
        disabled: Whether the rule is disabled
        nat_reflection: NAT reflection mode (enable, disable, purenat)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "interface": "interface",
            "protocol": "protocol",
            "destination": "destination",
            "destination_port": "destination_port",
            "target": "target",
            "local_port": "local_port",
            "source": "source",
            "description": "descr",
            "disabled": "disabled",
            "nat_reflection": "natreflection",
        }

        params = {
            "interface": interface,
            "protocol": protocol,
            "destination": destination,
            "destination_port": destination_port,
            "target": target,
            "local_port": local_port,
            "source": source,
            "description": description,
            "disabled": disabled,
            "nat_reflection": nat_reflection,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                api_field = field_map[param_name]
                if param_name == "interface":
                    updates[api_field] = [value] if isinstance(value, str) else value
                else:
                    updates[api_field] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        updates["id"] = port_forward_id
        control = ControlParameters(apply=apply_immediately)

        result = await client._make_request(
            "PATCH", "/firewall/nat/port_forward",
            data=updates, control=control
        )

        return {
            "success": True,
            "message": f"NAT port forward {port_forward_id} updated",
            "port_forward_id": port_forward_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update NAT port forward: {e}")
        return {"success": False, "error": str(e)}
