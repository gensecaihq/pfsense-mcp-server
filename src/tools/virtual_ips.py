"""Virtual IP tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import create_default_sort, create_pagination, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Virtual IPs
# ---------------------------------------------------------------------------


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_virtual_ips(
    search_term: Optional[str] = None,
    type_filter: Optional[str] = None,
    interface: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "subnet",
) -> Dict:
    """Search virtual IPs with filtering and pagination

    Args:
        search_term: General search across subnet/description (client-side filter)
        type_filter: Filter by VIP mode (ipalias, carp, proxyarp, other)
        interface: Filter by interface (wan, lan, opt1, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (subnet, mode, interface, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if type_filter:
            if type_filter not in ("ipalias", "carp", "proxyarp", "other"):
                return {"success": False, "error": "type_filter must be 'ipalias', 'carp', 'proxyarp', or 'other'"}
            filters.append(QueryFilter("mode", type_filter))

        if interface:
            filters.append(QueryFilter("interface", interface))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/virtual_ips",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        vips = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            vips = [
                v for v in vips
                if term_lower in v.get("subnet", "").lower()
                or term_lower in v.get("descr", "").lower()
                or term_lower in v.get("interface", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "type_filter": type_filter,
                "interface": interface,
            },
            "count": len(vips),
            "virtual_ips": vips,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search virtual IPs: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_virtual_ip(
    mode: str,
    interface: str,
    subnet: str,
    subnet_bits: int,
    type: str = "single",
    descr: Optional[str] = None,
    vhid: Optional[int] = None,
    advskew: Optional[int] = None,
    advbase: Optional[int] = None,
    password: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a virtual IP address

    Args:
        mode: VIP mode (ipalias, carp, proxyarp, other)
        interface: Interface to assign the VIP to (wan, lan, opt1, etc.)
        subnet: IP address for the virtual IP
        subnet_bits: Subnet mask bits (e.g., 32 for single host, 24 for /24)
        type: Address type (single, network)
        descr: Optional description
        vhid: VHID group number (required for CARP, 1-255)
        advskew: Advertisement skew for CARP (0-254, lower = higher priority)
        advbase: Advertisement base frequency for CARP (1-254 seconds)
        password: CARP password (required for CARP)
        apply_immediately: Whether to apply changes immediately
    """
    if mode not in ("ipalias", "carp", "proxyarp", "other"):
        return {"success": False, "error": "mode must be 'ipalias', 'carp', 'proxyarp', or 'other'"}

    if type not in ("single", "network"):
        return {"success": False, "error": "type must be 'single' or 'network'"}

    client = get_api_client()
    try:
        vip_data: Dict[str, Union[str, int, bool]] = {
            "mode": mode,
            "interface": interface,
            "subnet": subnet,
            "subnet_bits": subnet_bits,
            "type": type,
        }

        if descr:
            vip_data["descr"] = sanitize_description(descr)
        if vhid is not None:
            vip_data["vhid"] = vhid
        if advskew is not None:
            vip_data["advskew"] = advskew
        if advbase is not None:
            vip_data["advbase"] = advbase
        if password:
            vip_data["password"] = password

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/firewall/virtual_ip", vip_data, control)

        return {
            "success": True,
            "message": f"Virtual IP '{subnet}/{subnet_bits}' ({mode}) created on {interface}",
            "virtual_ip": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create virtual IP: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_virtual_ip(
    vip_id: int,
    mode: Optional[str] = None,
    interface: Optional[str] = None,
    subnet: Optional[str] = None,
    subnet_bits: Optional[int] = None,
    type: Optional[str] = None,
    descr: Optional[str] = None,
    vhid: Optional[int] = None,
    advskew: Optional[int] = None,
    advbase: Optional[int] = None,
    password: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing virtual IP by ID

    Args:
        vip_id: Virtual IP ID (from search_virtual_ips)
        mode: VIP mode (ipalias, carp, proxyarp, other)
        interface: Interface to assign the VIP to
        subnet: IP address for the virtual IP
        subnet_bits: Subnet mask bits
        type: Address type (single, network)
        descr: Description
        vhid: VHID group number (for CARP)
        advskew: Advertisement skew for CARP
        advbase: Advertisement base frequency for CARP
        password: CARP password
        apply_immediately: Whether to apply changes immediately
    """
    if mode is not None and mode not in ("ipalias", "carp", "proxyarp", "other"):
        return {"success": False, "error": "mode must be 'ipalias', 'carp', 'proxyarp', or 'other'"}

    if type is not None and type not in ("single", "network"):
        return {"success": False, "error": "type must be 'single' or 'network'"}

    client = get_api_client()
    try:
        params = {
            "mode": mode,
            "interface": interface,
            "subnet": subnet,
            "subnet_bits": subnet_bits,
            "type": type,
            "descr": descr,
            "vhid": vhid,
            "advskew": advskew,
            "advbase": advbase,
            "password": password,
        }

        updates: Dict[str, Union[str, int, bool]] = {}
        for param_name, value in params.items():
            if value is not None:
                if param_name == "descr" and isinstance(value, str):
                    updates[param_name] = sanitize_description(value)
                else:
                    updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/firewall/virtual_ip", vip_id, updates, control)

        return {
            "success": True,
            "message": f"Virtual IP {vip_id} updated",
            "vip_id": vip_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update virtual IP: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_virtual_ip(
    vip_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a virtual IP by ID. WARNING: This is irreversible.

    Args:
        vip_id: Virtual IP ID (from search_virtual_ips)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/firewall/virtual_ip", vip_id, control)

        return {
            "success": True,
            "message": f"Virtual IP {vip_id} deleted",
            "vip_id": vip_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query virtual IPs before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete virtual IP: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_virtual_ip_changes() -> Dict:
    """Apply pending virtual IP changes

    Use this after making changes with apply_immediately=False to batch-apply them.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/firewall/virtual_ip/apply")

        return {
            "success": True,
            "message": "Virtual IP changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply virtual IP changes: {e}")
        return {"success": False, "error": str(e)}
