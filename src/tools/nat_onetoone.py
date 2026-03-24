"""NAT 1:1 mapping tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# 1:1 NAT Mappings
# ---------------------------------------------------------------------------


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_nat_onetoone_mappings(
    search_term: Optional[str] = None,
    interface: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "interface",
) -> Dict:
    """Search 1:1 NAT mappings with filtering and pagination

    Args:
        search_term: General search across mapping description/source/destination (client-side filter)
        interface: Filter by interface (wan, lan, opt1, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (interface, external, source, destination, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if interface:
            filters.append(QueryFilter("interface", interface))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/nat/one_to_one/mappings",
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
                or term_lower in m.get("external", "").lower()
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
            "onetoone_mappings": mappings,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search 1:1 NAT mappings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_nat_onetoone_mapping(
    interface: str,
    external: str,
    source: str,
    type: Optional[str] = None,
    destination: Optional[str] = None,
    descr: Optional[str] = None,
    disabled: bool = False,
    apply_immediately: bool = True,
) -> Dict:
    """Create a 1:1 NAT mapping

    Args:
        interface: Interface for the mapping (wan, lan, opt1, etc.)
        external: External subnet (the public/translated address or subnet)
        source: Internal source network/address to map
        type: NAT type (e.g., "binat")
        destination: Destination filter for the mapping
        descr: Optional description
        disabled: Whether the mapping starts disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        mapping_data: Dict = {
            "interface": interface,
            "external": external,
            "source": source,
            "disabled": disabled,
        }

        if type:
            mapping_data["type"] = type
        if destination:
            mapping_data["destination"] = destination
        if descr:
            mapping_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/firewall/nat/one_to_one/mapping", mapping_data, control)

        return {
            "success": True,
            "message": f"1:1 NAT mapping created on {interface}: {source} <-> {external}",
            "onetoone_mapping": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create 1:1 NAT mapping: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_nat_onetoone_mapping(
    mapping_id: int,
    interface: Optional[str] = None,
    type: Optional[str] = None,
    external: Optional[str] = None,
    source: Optional[str] = None,
    destination: Optional[str] = None,
    descr: Optional[str] = None,
    disabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing 1:1 NAT mapping by ID

    Args:
        mapping_id: Mapping ID (from search_nat_onetoone_mappings)
        interface: Interface for the mapping
        type: NAT type (e.g., "binat")
        external: External subnet
        source: Internal source network/address
        destination: Destination filter
        descr: Description
        disabled: Whether the mapping is disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "interface": "interface",
            "type": "type",
            "external": "external",
            "source": "source",
            "destination": "destination",
            "descr": "descr",
            "disabled": "disabled",
        }

        params = {
            "interface": interface,
            "type": type,
            "external": external,
            "source": source,
            "destination": destination,
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
        result = await client.crud_update("/firewall/nat/one_to_one/mapping", mapping_id, updates, control)

        return {
            "success": True,
            "message": f"1:1 NAT mapping {mapping_id} updated",
            "mapping_id": mapping_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update 1:1 NAT mapping: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_nat_onetoone_mapping(
    mapping_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a 1:1 NAT mapping by ID. WARNING: This is irreversible.

    Args:
        mapping_id: Mapping ID (from search_nat_onetoone_mappings)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/firewall/nat/one_to_one/mapping", mapping_id, control)

        return {
            "success": True,
            "message": f"1:1 NAT mapping {mapping_id} deleted",
            "mapping_id": mapping_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query 1:1 NAT mappings before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete 1:1 NAT mapping: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Apply NAT 1:1 Changes
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_nat_onetoone_changes() -> Dict:
    """Apply pending 1:1 NAT changes

    Use this after making changes with apply_immediately=False to batch-apply them.
    This shares the firewall apply endpoint.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/firewall/apply")

        return {
            "success": True,
            "message": "1:1 NAT changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply 1:1 NAT changes: {e}")
        return {"success": False, "error": str(e)}
