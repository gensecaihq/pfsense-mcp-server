"""Alias tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import (
    VALID_ALIAS_TYPES,
    create_default_sort,
    create_pagination,
    validate_alias_addresses,
    validate_alias_name,
)
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_aliases(
    search_term: Optional[str] = None,
    alias_type: Optional[str] = None,
    containing_ip: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name"
) -> Dict:
    """Search aliases with advanced filtering options

    Args:
        search_term: Search in alias names or descriptions
        alias_type: Filter by alias type (host, network, port, url)
        containing_ip: Find aliases containing this IP address
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by
    """
    client = get_api_client()
    try:
        filters = []

        if alias_type:
            filters.append(QueryFilter("type", alias_type))

        if containing_ip:
            filters.append(QueryFilter("address", containing_ip, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        aliases = await client.get_aliases(
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )

        alias_list = aliases.get("data") or []

        # Client-side filtering: search_term matches name or description
        if search_term:
            term_lower = search_term.lower()
            alias_list = [
                a for a in alias_list
                if term_lower in a.get("name", "").lower()
                or term_lower in a.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "alias_type": alias_type,
                "containing_ip": containing_ip
            },
            "count": len(alias_list),
            "aliases": alias_list,
            "links": client.extract_links(aliases),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search aliases: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def manage_alias_addresses(
    alias_id: int,
    action: str,
    addresses: List[str]
) -> Dict:
    """Add or remove addresses from an existing alias

    Args:
        alias_id: ID of the alias to modify
        action: Action to perform ('add' or 'remove')
        addresses: List of addresses to add or remove
    """
    client = get_api_client()
    try:
        if action.lower() == "add":
            result = await client.add_to_alias(alias_id, addresses)
            message = f"Added {len(addresses)} addresses to alias {alias_id}"
        elif action.lower() == "remove":
            result = await client.remove_from_alias(alias_id, addresses)
            message = f"Removed {len(addresses)} addresses from alias {alias_id}"
        else:
            return {"success": False, "error": f"Invalid action '{action}'. Must be 'add' or 'remove'."}

        return {
            "success": True,
            "message": message,
            "alias_id": alias_id,
            "action": action,
            "addresses": addresses,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to manage alias addresses: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_alias(
    name: str,
    alias_type: str,
    addresses: List[str],
    description: Optional[str] = None,
    details: Optional[List[str]] = None,
    apply_immediately: bool = True
) -> Dict:
    """Create a new firewall alias

    Args:
        name: Alias name (max 31 characters, alphanumeric and underscores)
        alias_type: Type of alias (host, network, port)
        addresses: List of initial entries (IPs, networks, or ports depending on type)
        description: Optional description of the alias
        details: Optional per-entry descriptions (same length as addresses)
        apply_immediately: Whether to apply changes immediately
    """
    # Validate alias name
    name_error = validate_alias_name(name)
    if name_error:
        return {"success": False, "error": name_error}

    # Validate alias type
    if alias_type not in VALID_ALIAS_TYPES:
        return {
            "success": False,
            "error": f"Invalid alias_type '{alias_type}'. Must be one of: {', '.join(sorted(VALID_ALIAS_TYPES))}",
        }

    # Validate addresses match the alias type
    addr_error = validate_alias_addresses(alias_type, addresses)
    if addr_error:
        return {"success": False, "error": addr_error}

    client = get_api_client()
    try:
        alias_data = {
            "name": name,
            "type": alias_type,
            "address": addresses,
        }

        if description:
            alias_data["descr"] = description

        if details:
            alias_data["detail"] = details

        control = ControlParameters(apply=apply_immediately)
        result = await client.create_alias(alias_data, control)

        return {
            "success": True,
            "message": f"Alias '{name}' created",
            "alias": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create alias: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_alias(
    alias_id: int,
    name: Optional[str] = None,
    alias_type: Optional[str] = None,
    addresses: Optional[List[str]] = None,
    description: Optional[str] = None,
    details: Optional[List[str]] = None,
    apply_immediately: bool = True
) -> Dict:
    """Update an existing alias by ID

    Args:
        alias_id: Alias ID (array index from search_aliases)
        name: New alias name
        alias_type: New alias type (host, network, port)
        addresses: New list of addresses
        description: New description
        details: New per-entry descriptions
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "name": "name",
            "alias_type": "type",
            "addresses": "address",
            "description": "descr",
            "details": "detail",
        }

        params = {
            "name": name,
            "alias_type": alias_type,
            "addresses": addresses,
            "description": description,
            "details": details,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.update_alias(alias_id, updates, control)

        return {
            "success": True,
            "message": f"Alias {alias_id} updated",
            "alias_id": alias_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update alias: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_alias(
    alias_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an alias by ID. WARNING: This is irreversible.

    Args:
        alias_id: Alias ID (array index from search_aliases)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        result = await client.delete_alias(alias_id, apply_immediately)

        return {
            "success": True,
            "message": f"Alias {alias_id} deleted",
            "alias_id": alias_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query aliases before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to delete alias: {e}")
        return {"success": False, "error": str(e)}
