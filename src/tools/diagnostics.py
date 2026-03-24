"""Diagnostics tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import create_default_sort, create_pagination, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Ping Diagnostic
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def run_ping_diagnostic(
    host: str,
    count: int = 4,
) -> Dict:
    """Run a ping diagnostic from the pfSense firewall

    Args:
        host: Hostname or IP address to ping
        count: Number of ping packets to send (default 4)
    """
    if count < 1 or count > 100:
        return {"success": False, "error": "count must be between 1 and 100"}

    client = get_api_client()
    try:
        ping_data: Dict[str, Union[str, int]] = {
            "host": host,
            "count": count,
        }

        result = await client.crud_create("/diagnostics/ping", ping_data)

        return {
            "success": True,
            "message": f"Ping to {host} completed ({count} packets)",
            "ping_result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to run ping diagnostic: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# System Power
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def reboot_system(
    confirm: bool = False,
) -> Dict:
    """Reboot the pfSense system. WARNING: This will cause a service interruption.

    Args:
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": "Will reboot the pfSense system, causing a service interruption.",
        }

    client = get_api_client()
    try:
        result = await client.crud_create("/diagnostics/reboot", {})

        return {
            "success": True,
            "message": "System reboot initiated",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to reboot system: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def halt_system(
    confirm: bool = False,
) -> Dict:
    """Halt (shut down) the pfSense system. WARNING: This will power off the system.

    Args:
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": "Will halt the pfSense system, powering it off completely.",
        }

    client = get_api_client()
    try:
        result = await client.crud_create("/diagnostics/halt_system", {})

        return {
            "success": True,
            "message": "System halt initiated",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to halt system: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Config History
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_config_history(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "time",
) -> Dict:
    """Get configuration history revisions with pagination

    Args:
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (time, description, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/diagnostics/config_history/revisions",
            sort=sort,
            pagination=pagination,
        )

        revisions = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "count": len(revisions),
            "revisions": revisions,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get config history: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_config_revision(
    revision_id: int,
) -> Dict:
    """Get a specific configuration history revision by ID

    Args:
        revision_id: Revision ID (from get_config_history)
    """
    client = get_api_client()
    try:
        result = await client.crud_get_settings(
            f"/diagnostics/config_history/revision",
            params={"id": revision_id},
        )

        return {
            "success": True,
            "revision_id": revision_id,
            "revision": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get config revision: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_config_revision(
    revision_id: int,
    confirm: bool = False,
) -> Dict:
    """Delete a configuration history revision by ID. WARNING: This is irreversible.

    Args:
        revision_id: Revision ID (from get_config_history)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will permanently delete config revision {revision_id}.",
        }

    client = get_api_client()
    try:
        result = await client.crud_delete("/diagnostics/config_history/revision", revision_id)

        return {
            "success": True,
            "message": f"Config revision {revision_id} deleted",
            "revision_id": revision_id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query config history before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete config revision: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# PF Tables
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_pf_tables(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search pf firewall tables with filtering and pagination

    Args:
        search_term: General search across table name (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, count, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/diagnostics/tables",
            sort=sort,
            pagination=pagination,
        )

        tables = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            tables = [
                t for t in tables
                if term_lower in t.get("name", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(tables),
            "pf_tables": tables,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search pf tables: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_pf_table(
    name: str,
) -> Dict:
    """Get the contents of a specific pf firewall table

    Args:
        name: Table name (from search_pf_tables, e.g., "bogons", "sshlockout", "virusprot")
    """
    client = get_api_client()
    try:
        result = await client.crud_get_settings(
            "/diagnostics/table",
            params={"name": name},
        )

        return {
            "success": True,
            "table_name": name,
            "table": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get pf table '{name}': {e}")
        return {"success": False, "error": str(e)}
