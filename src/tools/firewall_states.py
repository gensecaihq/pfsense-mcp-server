"""Firewall state tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Firewall States
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_firewall_states(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "id",
) -> Dict:
    """Search firewall states (active connections) with filtering and pagination

    Args:
        search_term: Search across state source/destination/protocol (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (id, protocol, source, destination, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/states",
            sort=sort,
            pagination=pagination,
        )

        states = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            states = [
                s for s in states
                if term_lower in str(s.get("source", "")).lower()
                or term_lower in str(s.get("destination", "")).lower()
                or term_lower in str(s.get("protocol", "")).lower()
                or term_lower in str(s.get("interface", "")).lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(states),
            "states": states,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search firewall states: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_firewall_state(
    id: str,
    confirm: bool = False,
) -> Dict:
    """Delete a specific firewall state (active connection) by ID. WARNING: This is irreversible.

    Terminating a state will immediately drop the associated connection.

    Args:
        id: State ID (from search_firewall_states)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will terminate firewall state {id}, dropping the associated connection.",
        }

    client = get_api_client()
    try:
        control = ControlParameters(apply=False)
        result = await client.crud_delete("/firewall/state", id, control)

        return {
            "success": True,
            "message": f"Firewall state {id} deleted (connection terminated)",
            "state_id": id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query firewall states before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete firewall state: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Firewall State Size
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_firewall_state_size() -> Dict:
    """Get the current firewall state table size and limits

    Returns the current number of active states and the configured maximum.
    """
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/firewall/states/size")

        return {
            "success": True,
            "state_size": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get firewall state size: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Firewall Advanced Settings
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_firewall_advanced_settings() -> Dict:
    """Get firewall advanced settings

    Returns advanced firewall configuration including optimization mode,
    state timeout values, and other tuning parameters.
    """
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/firewall/advanced_settings")

        return {
            "success": True,
            "advanced_settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get firewall advanced settings: {e}")
        return {"success": False, "error": str(e)}
