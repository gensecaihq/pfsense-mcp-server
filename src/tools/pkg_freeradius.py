"""FreeRADIUS server package tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_freeradius_users(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "username",
) -> Dict:
    """Search FreeRADIUS users with filtering and pagination

    Requires the FreeRADIUS package to be installed on pfSense.

    Args:
        search_term: Search in username/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (username, ip, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/freeradius/users",
            sort=sort,
            pagination=pagination,
        )

        users = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            users = [
                u for u in users
                if term_lower in u.get("username", "").lower()
                or term_lower in u.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(users),
            "users": users,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search FreeRADIUS users: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_freeradius_user(
    username: str,
    password: str,
    ip: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a FreeRADIUS user

    Args:
        username: RADIUS username
        password: RADIUS password
        ip: Optional assigned IP address for the user
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        user_data: Dict = {
            "username": username,
            "password": password,
        }

        if ip:
            user_data["ip"] = ip
        if descr:
            user_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/services/freeradius/user", user_data, control)

        return {
            "success": True,
            "message": f"FreeRADIUS user '{username}' created",
            "user": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create FreeRADIUS user: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_freeradius_user(
    user_id: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    ip: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing FreeRADIUS user by ID

    Args:
        user_id: User ID (from search_freeradius_users)
        username: RADIUS username
        password: RADIUS password
        ip: Assigned IP address
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "username": username,
            "password": password,
            "ip": ip,
            "descr": descr,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                if param_name == "descr":
                    updates[param_name] = sanitize_description(value)
                else:
                    updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/services/freeradius/user", user_id, updates, control)

        return {
            "success": True,
            "message": f"FreeRADIUS user {user_id} updated",
            "user_id": user_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update FreeRADIUS user: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_freeradius_user(
    user_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a FreeRADIUS user by ID. WARNING: This is irreversible.

    Args:
        user_id: User ID (from search_freeradius_users)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/services/freeradius/user", user_id, control)

        return {
            "success": True,
            "message": f"FreeRADIUS user {user_id} deleted",
            "user_id": user_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query users before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete FreeRADIUS user: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Clients (NAS devices)
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_freeradius_clients(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "shortname",
) -> Dict:
    """Search FreeRADIUS clients (NAS devices) with filtering and pagination

    Args:
        search_term: Search in client shortname/IP/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (shortname, ip, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/freeradius/clients",
            sort=sort,
            pagination=pagination,
        )

        clients = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            clients = [
                c for c in clients
                if term_lower in c.get("shortname", "").lower()
                or term_lower in c.get("ip", "").lower()
                or term_lower in c.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(clients),
            "clients": clients,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search FreeRADIUS clients: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_freeradius_client(
    ip: str,
    secret: str,
    shortname: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a FreeRADIUS client (NAS device)

    Args:
        ip: Client IP address or network (e.g., '192.168.1.1' or '192.168.1.0/24')
        secret: Shared secret for RADIUS authentication
        shortname: Short name / identifier for the client
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        client_data: Dict = {
            "ip": ip,
            "secret": secret,
        }

        if shortname:
            client_data["shortname"] = shortname
        if descr:
            client_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/services/freeradius/client", client_data, control)

        return {
            "success": True,
            "message": f"FreeRADIUS client '{shortname or ip}' created",
            "client": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create FreeRADIUS client: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_freeradius_client(
    client_id: int,
    ip: Optional[str] = None,
    secret: Optional[str] = None,
    shortname: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing FreeRADIUS client by ID

    Args:
        client_id: Client ID (from search_freeradius_clients)
        ip: Client IP address or network
        secret: Shared secret
        shortname: Short name / identifier
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "ip": ip,
            "secret": secret,
            "shortname": shortname,
            "descr": descr,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                if param_name == "descr":
                    updates[param_name] = sanitize_description(value)
                else:
                    updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/services/freeradius/client", client_id, updates, control)

        return {
            "success": True,
            "message": f"FreeRADIUS client {client_id} updated",
            "client_id": client_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update FreeRADIUS client: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_freeradius_client(
    client_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a FreeRADIUS client by ID. WARNING: This is irreversible.

    Args:
        client_id: Client ID (from search_freeradius_clients)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/services/freeradius/client", client_id, control)

        return {
            "success": True,
            "message": f"FreeRADIUS client {client_id} deleted",
            "client_id": client_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query clients before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete FreeRADIUS client: {e}")
        return {"success": False, "error": str(e)}
