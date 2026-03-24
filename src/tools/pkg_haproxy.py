"""HAProxy load balancer package tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_haproxy_backends(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search HAProxy backends with filtering and pagination

    Requires the HAProxy package to be installed on pfSense.

    Args:
        search_term: Search in backend name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, mode, balance, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/haproxy/backends",
            sort=sort,
            pagination=pagination,
        )

        backends = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            backends = [
                b for b in backends
                if term_lower in b.get("name", "").lower()
                or term_lower in b.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(backends),
            "backends": backends,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search HAProxy backends: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_haproxy_backend(
    name: str,
    mode: str = "http",
    balance: Optional[str] = None,
    check_type: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an HAProxy backend pool

    Args:
        name: Backend name (alphanumeric and underscores only)
        mode: Protocol mode ('http' or 'tcp')
        balance: Load balancing algorithm (roundrobin, leastconn, source, etc.)
        check_type: Health check type (HTTP, TCP, SSL, none, etc.)
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    if mode not in ("http", "tcp"):
        return {"success": False, "error": "mode must be 'http' or 'tcp'"}

    client = get_api_client()
    try:
        backend_data: Dict = {
            "name": name,
            "mode": mode,
        }

        if balance:
            backend_data["balance"] = balance
        if check_type:
            backend_data["check_type"] = check_type
        if descr:
            backend_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/services/haproxy/backend", backend_data, control)

        return {
            "success": True,
            "message": f"HAProxy backend '{name}' created (mode={mode})",
            "backend": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create HAProxy backend: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_haproxy_backend(
    backend_id: int,
    name: Optional[str] = None,
    mode: Optional[str] = None,
    balance: Optional[str] = None,
    check_type: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing HAProxy backend by ID

    Args:
        backend_id: Backend ID (from search_haproxy_backends)
        name: Backend name
        mode: Protocol mode ('http' or 'tcp')
        balance: Load balancing algorithm
        check_type: Health check type
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    if mode is not None and mode not in ("http", "tcp"):
        return {"success": False, "error": "mode must be 'http' or 'tcp'"}

    client = get_api_client()
    try:
        params = {
            "name": name,
            "mode": mode,
            "balance": balance,
            "check_type": check_type,
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
        result = await client.crud_update("/services/haproxy/backend", backend_id, updates, control)

        return {
            "success": True,
            "message": f"HAProxy backend {backend_id} updated",
            "backend_id": backend_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update HAProxy backend: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_haproxy_backend(
    backend_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Delete an HAProxy backend by ID. WARNING: This is irreversible.

    Args:
        backend_id: Backend ID (from search_haproxy_backends)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will permanently delete HAProxy backend {backend_id}.",
        }

    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/services/haproxy/backend", backend_id, control)

        return {
            "success": True,
            "message": f"HAProxy backend {backend_id} deleted",
            "backend_id": backend_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query backends before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete HAProxy backend: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Backend Servers
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_haproxy_backend_servers(
    parent_id: int,
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search servers within an HAProxy backend

    Args:
        parent_id: Backend ID to list servers for
        search_term: Search in server name/address (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, address, port, weight, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        filters = [QueryFilter("parent_id", str(parent_id))]

        result = await client.crud_list(
            "/services/haproxy/backend/servers",
            filters=filters,
            sort=sort,
            pagination=pagination,
        )

        servers = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            servers = [
                s for s in servers
                if term_lower in s.get("name", "").lower()
                or term_lower in s.get("address", "").lower()
            ]

        return {
            "success": True,
            "parent_id": parent_id,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(servers),
            "servers": servers,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search HAProxy backend servers: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_haproxy_backend_server(
    action: str,
    parent_id: int,
    name: Optional[str] = None,
    address: Optional[str] = None,
    port: Optional[int] = None,
    ssl: Optional[bool] = None,
    weight: Optional[int] = None,
    server_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Add or remove a server from an HAProxy backend

    Args:
        action: Action to perform ('create' or 'delete')
        parent_id: Parent backend ID
        name: Server name (required for create)
        address: Server IP address or hostname (required for create)
        port: Server port (required for create)
        ssl: Enable SSL for backend connection (used for create)
        weight: Server weight for load balancing (used for create)
        server_id: Server ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not name:
                return {"success": False, "error": "name is required for create action"}
            if not address:
                return {"success": False, "error": "address is required for create action"}
            if port is None:
                return {"success": False, "error": "port is required for create action"}

            server_data: Dict = {
                "parent_id": parent_id,
                "name": name,
                "address": address,
                "port": port,
            }
            if ssl is not None:
                server_data["ssl"] = ssl
            if weight is not None:
                server_data["weight"] = weight

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create("/services/haproxy/backend/server", server_data, control)

            return {
                "success": True,
                "message": f"Server '{name}' ({address}:{port}) added to backend {parent_id}",
                "server": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if server_id is None:
                return {"success": False, "error": "server_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete server {server_id} from backend {parent_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete(
                "/services/haproxy/backend/server", server_id, control,
                extra_data={"parent_id": parent_id},
            )

            return {
                "success": True,
                "message": f"Server {server_id} removed from backend {parent_id}",
                "server_id": server_id,
                "parent_id": parent_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query servers before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }
    except Exception as e:
        logger.error(f"Failed to manage HAProxy backend server: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Frontends
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_haproxy_frontends(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search HAProxy frontends with filtering and pagination

    Args:
        search_term: Search in frontend name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, descr, type, status, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/haproxy/frontends",
            sort=sort,
            pagination=pagination,
        )

        frontends = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            frontends = [
                f for f in frontends
                if term_lower in f.get("name", "").lower()
                or term_lower in f.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(frontends),
            "frontends": frontends,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search HAProxy frontends: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_haproxy_frontend(
    name: str,
    descr: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    backend: Optional[str] = None,
    bind_addresses: Optional[List[Dict]] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an HAProxy frontend listener

    Args:
        name: Frontend name
        descr: Optional description
        type: Frontend type (http, https, tcp, ssl, etc.)
        status: Frontend status (active, disabled)
        backend: Default backend name to forward traffic to
        bind_addresses: List of bind address dicts, e.g. [{"address": "0.0.0.0", "port": "80"}]
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        frontend_data: Dict = {"name": name}

        if descr:
            frontend_data["descr"] = sanitize_description(descr)
        if type:
            frontend_data["type"] = type
        if status:
            frontend_data["status"] = status
        if backend:
            frontend_data["backend"] = backend
        if bind_addresses:
            frontend_data["bind_addresses"] = bind_addresses

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/services/haproxy/frontend", frontend_data, control)

        return {
            "success": True,
            "message": f"HAProxy frontend '{name}' created",
            "frontend": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create HAProxy frontend: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_haproxy_frontend(
    frontend_id: int,
    name: Optional[str] = None,
    descr: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    backend: Optional[str] = None,
    bind_addresses: Optional[List[Dict]] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing HAProxy frontend by ID

    Args:
        frontend_id: Frontend ID (from search_haproxy_frontends)
        name: Frontend name
        descr: Description
        type: Frontend type
        status: Frontend status (active, disabled)
        backend: Default backend name
        bind_addresses: List of bind address dicts
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "name": name,
            "descr": descr,
            "type": type,
            "status": status,
            "backend": backend,
            "bind_addresses": bind_addresses,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                if param_name == "descr" and isinstance(value, str):
                    updates[param_name] = sanitize_description(value)
                else:
                    updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/services/haproxy/frontend", frontend_id, updates, control)

        return {
            "success": True,
            "message": f"HAProxy frontend {frontend_id} updated",
            "frontend_id": frontend_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update HAProxy frontend: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_haproxy_frontend(
    frontend_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Delete an HAProxy frontend by ID. WARNING: This is irreversible.

    Args:
        frontend_id: Frontend ID (from search_haproxy_frontends)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will permanently delete HAProxy frontend {frontend_id}.",
        }

    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/services/haproxy/frontend", frontend_id, control)

        return {
            "success": True,
            "message": f"HAProxy frontend {frontend_id} deleted",
            "frontend_id": frontend_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query frontends before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete HAProxy frontend: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_haproxy_files(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search HAProxy files (certificates, error pages, Lua scripts, etc.)

    Args:
        search_term: Search in file name (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/haproxy/files",
            sort=sort,
            pagination=pagination,
        )

        files = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            files = [
                f for f in files
                if term_lower in f.get("name", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(files),
            "files": files,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search HAProxy files: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_haproxy_file(
    action: str,
    name: Optional[str] = None,
    content: Optional[str] = None,
    file_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Create or delete an HAProxy file (certificate, error page, Lua script, etc.)

    Args:
        action: Action to perform ('create' or 'delete')
        name: File name (required for create)
        content: File content (used for create)
        file_id: File ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not name:
                return {"success": False, "error": "name is required for create action"}

            file_data: Dict = {"name": name}
            if content is not None:
                file_data["content"] = content

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create("/services/haproxy/file", file_data, control)

            return {
                "success": True,
                "message": f"HAProxy file '{name}' created",
                "file": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if file_id is None:
                return {"success": False, "error": "file_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete HAProxy file {file_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete("/services/haproxy/file", file_id, control)

            return {
                "success": True,
                "message": f"HAProxy file {file_id} deleted",
                "file_id": file_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query files before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }
    except Exception as e:
        logger.error(f"Failed to manage HAProxy file: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Settings & Apply
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_haproxy_settings() -> Dict:
    """Get the current HAProxy service settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/services/haproxy/settings")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get HAProxy settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_haproxy_settings(
    enable: Optional[bool] = None,
    maxconn: Optional[int] = None,
    nbthread: Optional[int] = None,
    hard_stop_after: Optional[str] = None,
    localstats_enabled: Optional[bool] = None,
    localstats_port: Optional[int] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update HAProxy service settings

    Args:
        enable: Enable or disable the HAProxy service
        maxconn: Maximum number of concurrent connections
        nbthread: Number of threads
        hard_stop_after: Hard stop timeout (e.g., '30s', '1m')
        localstats_enabled: Enable local statistics page
        localstats_port: Local statistics port
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "enable": enable,
            "maxconn": maxconn,
            "nbthread": nbthread,
            "hard_stop_after": hard_stop_after,
            "localstats_enabled": localstats_enabled,
            "localstats_port": localstats_port,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/services/haproxy/settings", updates, control)

        return {
            "success": True,
            "message": "HAProxy settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update HAProxy settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_haproxy_changes() -> Dict:
    """Apply pending HAProxy configuration changes

    Use this after making changes with apply_immediately=False to batch-apply them.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/services/haproxy/apply")

        return {
            "success": True,
            "message": "HAProxy changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply HAProxy changes: {e}")
        return {"success": False, "error": str(e)}
