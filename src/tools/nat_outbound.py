"""NAT outbound mapping tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Outbound NAT Mappings
# ---------------------------------------------------------------------------


from ..guardrails import guarded
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_nat_outbound_mappings(
    search_term: Optional[str] = None,
    interface: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "interface",
) -> Dict:
    """Search outbound NAT mappings with filtering and pagination

    Args:
        search_term: General search across mapping description/source/destination (client-side filter)
        interface: Filter by interface (wan, lan, opt1, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (interface, source, destination, target, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if interface:
            filters.append(QueryFilter("interface", interface))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/nat/outbound/mappings",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        mappings = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            mappings = [
                m for m in mappings
                if term_lower in m.get("descr", "").lower()
                or term_lower in m.get("source", "").lower()
                or term_lower in m.get("destination", "").lower()
                or term_lower in m.get("target", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "interface": interface,
            },
            "count": len(mappings),
            "outbound_mappings": mappings,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search outbound NAT mappings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_nat_outbound_mapping(
    interface: str,
    source: str,
    sourceport: Optional[str] = None,
    destination: Optional[str] = None,
    dstport: Optional[str] = None,
    target: Optional[str] = None,
    targetip: Optional[str] = None,
    targetip_subnet: Optional[int] = None,
    poolopts: Optional[str] = None,
    protocol: Optional[str] = None,
    descr: Optional[str] = None,
    disabled: bool = False,
    apply_immediately: bool = True,
) -> Dict:
    """Create an outbound NAT mapping

    Args:
        interface: Interface for the mapping (wan, lan, opt1, etc.)
        source: Source network/address (e.g., "192.168.1.0/24", "any")
        sourceport: Source port or port range
        destination: Destination network/address
        dstport: Destination port or port range
        target: Translation target type
        targetip: Translation target IP address
        targetip_subnet: Translation target subnet mask
        poolopts: Pool options for multiple addresses (round-robin, etc.)
        protocol: Protocol (tcp, udp, tcp/udp, etc.)
        descr: Optional description
        disabled: Whether the mapping starts disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        mapping_data: Dict = {
            "interface": interface,
            "source": source,
            "disabled": disabled,
        }

        if sourceport:
            mapping_data["sourceport"] = sourceport
        if destination:
            mapping_data["destination"] = destination
        if dstport:
            mapping_data["dstport"] = dstport
        if target:
            mapping_data["target"] = target
        if targetip:
            mapping_data["targetip"] = targetip
        if targetip_subnet is not None:
            mapping_data["targetip_subnet"] = targetip_subnet
        if poolopts:
            mapping_data["poolopts"] = poolopts
        if protocol:
            mapping_data["protocol"] = protocol
        if descr:
            mapping_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/firewall/nat/outbound/mapping", mapping_data, control)

        return {
            "success": True,
            "message": f"Outbound NAT mapping created on {interface} for source {source}",
            "outbound_mapping": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create outbound NAT mapping: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_nat_outbound_mapping(
    mapping_id: int,
    interface: Optional[str] = None,
    source: Optional[str] = None,
    sourceport: Optional[str] = None,
    destination: Optional[str] = None,
    dstport: Optional[str] = None,
    target: Optional[str] = None,
    targetip: Optional[str] = None,
    targetip_subnet: Optional[int] = None,
    poolopts: Optional[str] = None,
    protocol: Optional[str] = None,
    descr: Optional[str] = None,
    disabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing outbound NAT mapping by ID

    Args:
        mapping_id: Mapping ID (from search_nat_outbound_mappings)
        interface: Interface for the mapping
        source: Source network/address
        sourceport: Source port or port range
        destination: Destination network/address
        dstport: Destination port or port range
        target: Translation target type
        targetip: Translation target IP address
        targetip_subnet: Translation target subnet mask
        poolopts: Pool options for multiple addresses
        protocol: Protocol (tcp, udp, tcp/udp, etc.)
        descr: Description
        disabled: Whether the mapping is disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "interface": "interface",
            "source": "source",
            "sourceport": "sourceport",
            "destination": "destination",
            "dstport": "dstport",
            "target": "target",
            "targetip": "targetip",
            "targetip_subnet": "targetip_subnet",
            "poolopts": "poolopts",
            "protocol": "protocol",
            "descr": "descr",
            "disabled": "disabled",
        }

        params = {
            "interface": interface,
            "source": source,
            "sourceport": sourceport,
            "destination": destination,
            "dstport": dstport,
            "target": target,
            "targetip": targetip,
            "targetip_subnet": targetip_subnet,
            "poolopts": poolopts,
            "protocol": protocol,
            "descr": descr,
            "disabled": disabled,
        }

        updates: Dict = {}
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
        result = await client.crud_update("/firewall/nat/outbound/mapping", mapping_id, updates, control)

        return {
            "success": True,
            "message": f"Outbound NAT mapping {mapping_id} updated",
            "mapping_id": mapping_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update outbound NAT mapping: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_nat_outbound_mapping(
    mapping_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an outbound NAT mapping by ID. WARNING: This is irreversible.

    Args:
        mapping_id: Mapping ID (from search_nat_outbound_mappings)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/firewall/nat/outbound/mapping", mapping_id, control)

        return {
            "success": True,
            "message": f"Outbound NAT mapping {mapping_id} deleted",
            "mapping_id": mapping_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query outbound NAT mappings before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete outbound NAT mapping: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Outbound NAT Mode
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_nat_outbound_mode() -> Dict:
    """Get the current outbound NAT mode (automatic, hybrid, advanced, or disabled)"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/firewall/nat/outbound/mode")

        return {
            "success": True,
            "outbound_mode": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get outbound NAT mode: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_nat_outbound_mode(
    mode: str,
    apply_immediately: bool = True,
) -> Dict:
    """Update the outbound NAT mode

    Args:
        mode: Outbound NAT mode (automatic, hybrid, advanced, disabled)
        apply_immediately: Whether to apply changes immediately
    """
    valid_modes = ("automatic", "hybrid", "advanced", "disabled")
    if mode not in valid_modes:
        return {
            "success": False,
            "error": f"mode must be one of: {', '.join(valid_modes)}",
        }

    client = get_api_client()
    try:
        updates: Dict = {"mode": mode}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/firewall/nat/outbound/mode", updates, control)

        return {
            "success": True,
            "message": f"Outbound NAT mode updated to '{mode}'",
            "fields_updated": ["mode"],
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update outbound NAT mode: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Apply NAT Changes
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_nat_changes() -> Dict:
    """Apply pending NAT changes (outbound mappings, mode changes)

    Use this after making changes with apply_immediately=False to batch-apply them.
    This shares the firewall apply endpoint.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/firewall/apply")

        return {
            "success": True,
            "message": "NAT changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply NAT changes: {e}")
        return {"success": False, "error": str(e)}
