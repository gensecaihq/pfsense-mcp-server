"""DHCP advanced features tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# DHCP Address Pools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_dhcp_address_pools(
    parent_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "range_from",
) -> Dict:
    """Search DHCP server address pools with filtering and pagination

    Args:
        parent_id: Filter by parent interface (e.g., 'lan', 'opt1')
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (range_from, range_to, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        if parent_id:
            filters.append(QueryFilter("parent_id", parent_id))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/dhcp_server/address_pools",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        pools = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"parent_id": parent_id},
            "count": len(pools),
            "address_pools": pools,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search DHCP address pools: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_dhcp_address_pool(
    parent_id: str,
    range_from: str,
    range_to: str,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a DHCP address pool for an interface

    Args:
        parent_id: Parent interface (e.g., 'lan', 'opt1')
        range_from: Start IP address of the pool range
        range_to: End IP address of the pool range
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        pool_data: Dict = {
            "parent_id": parent_id,
            "range_from": range_from,
            "range_to": range_to,
        }

        if descr:
            pool_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(
            "/services/dhcp_server/address_pool", pool_data, control
        )

        return {
            "success": True,
            "message": f"DHCP address pool created: {range_from} - {range_to} on {parent_id}",
            "address_pool": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create DHCP address pool: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_dhcp_address_pool(
    pool_id: int,
    range_from: Optional[str] = None,
    range_to: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing DHCP address pool by ID

    Args:
        pool_id: Address pool ID (from search_dhcp_address_pools)
        range_from: Start IP address of the pool range
        range_to: End IP address of the pool range
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if range_from is not None:
            updates["range_from"] = range_from
        if range_to is not None:
            updates["range_to"] = range_to
        if descr is not None:
            updates["descr"] = sanitize_description(descr)

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(
            "/services/dhcp_server/address_pool", pool_id, updates, control
        )

        return {
            "success": True,
            "message": f"DHCP address pool {pool_id} updated",
            "pool_id": pool_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DHCP address pool: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_dhcp_address_pool(
    pool_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Delete a DHCP address pool by ID. WARNING: This is irreversible.

    Args:
        pool_id: Address pool ID (from search_dhcp_address_pools)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will permanently delete DHCP address pool {pool_id}.",
        }

    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(
            "/services/dhcp_server/address_pool", pool_id, control
        )

        return {
            "success": True,
            "message": f"DHCP address pool {pool_id} deleted",
            "pool_id": pool_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query address pools before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete DHCP address pool: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# DHCP Custom Options
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_dhcp_custom_options(
    parent_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "number",
) -> Dict:
    """Search DHCP server custom options with filtering and pagination

    Args:
        parent_id: Filter by parent interface (e.g., 'lan', 'opt1')
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (number, type, value, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        if parent_id:
            filters.append(QueryFilter("parent_id", parent_id))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/dhcp_server/custom_options",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        options = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"parent_id": parent_id},
            "count": len(options),
            "custom_options": options,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search DHCP custom options: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_dhcp_custom_option(
    parent_id: str,
    number: int,
    type: str,
    value: str,
    apply_immediately: bool = True,
) -> Dict:
    """Create a DHCP custom option

    Args:
        parent_id: Parent interface (e.g., 'lan', 'opt1')
        number: DHCP option number (e.g., 66 for TFTP server, 150 for Cisco TFTP)
        type: Option type (e.g., 'text', 'string', 'boolean', 'unsigned integer 8', 'ip-address')
        value: Option value
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        option_data: Dict = {
            "parent_id": parent_id,
            "number": number,
            "type": type,
            "value": value,
        }

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(
            "/services/dhcp_server/custom_option", option_data, control
        )

        return {
            "success": True,
            "message": f"DHCP custom option {number} created on {parent_id}",
            "custom_option": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create DHCP custom option: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_dhcp_custom_option(
    option_id: int,
    number: Optional[int] = None,
    type: Optional[str] = None,
    value: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing DHCP custom option by ID

    Args:
        option_id: Custom option ID (from search_dhcp_custom_options)
        number: DHCP option number
        type: Option type
        value: Option value
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if number is not None:
            updates["number"] = number
        if type is not None:
            updates["type"] = type
        if value is not None:
            updates["value"] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(
            "/services/dhcp_server/custom_option", option_id, updates, control
        )

        return {
            "success": True,
            "message": f"DHCP custom option {option_id} updated",
            "option_id": option_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DHCP custom option: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_dhcp_custom_option(
    option_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Delete a DHCP custom option by ID. WARNING: This is irreversible.

    Args:
        option_id: Custom option ID (from search_dhcp_custom_options)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will permanently delete DHCP custom option {option_id}.",
        }

    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(
            "/services/dhcp_server/custom_option", option_id, control
        )

        return {
            "success": True,
            "message": f"DHCP custom option {option_id} deleted",
            "option_id": option_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query custom options before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete DHCP custom option: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Apply DHCP Changes
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_dhcp_changes() -> Dict:
    """Apply pending DHCP server changes

    Use this after making changes with apply_immediately=False to batch-apply them.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/services/dhcp_server/apply")

        return {
            "success": True,
            "message": "DHCP server changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply DHCP changes: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# DHCP Backend
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_dhcp_backend(
    dhcpbackend: str,
    apply_immediately: bool = True,
) -> Dict:
    """Update the DHCP server backend (ISC DHCP vs Kea)

    Args:
        dhcpbackend: DHCP backend to use ('isc' for ISC DHCP, 'kea' for Kea DHCP)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {
            "dhcpbackend": dhcpbackend,
        }

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings(
            "/services/dhcp_server/backend", updates, control
        )

        return {
            "success": True,
            "message": f"DHCP backend updated to '{dhcpbackend}'",
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DHCP backend: {e}")
        return {"success": False, "error": str(e)}
