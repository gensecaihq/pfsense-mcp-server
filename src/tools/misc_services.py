"""Miscellaneous services tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description, normalize_mac_address
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# NTP Settings
# ---------------------------------------------------------------------------


from ..guardrails import guarded
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_ntp_settings() -> Dict:
    """Get the NTP service settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/services/ntp/settings")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get NTP settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_ntp_settings(
    enable: Optional[bool] = None,
    interface: Optional[List[str]] = None,
    orphan: Optional[int] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the NTP service settings

    Args:
        enable: Whether to enable the NTP service
        interface: List of interfaces to listen on
        orphan: Orphan stratum value
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if enable is not None:
            updates["enable"] = enable
        if interface is not None:
            updates["interface"] = interface
        if orphan is not None:
            updates["orphan"] = orphan
        if descr is not None:
            updates["descr"] = sanitize_description(descr)

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/services/ntp/settings", updates, control)

        return {
            "success": True,
            "message": "NTP settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update NTP settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# NTP Time Servers
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_ntp_time_servers(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "timeserver",
) -> Dict:
    """Search NTP time servers with pagination

    Args:
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (timeserver, type, prefer, noselect, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/ntp/time_servers",
            sort=sort,
            pagination=pagination,
        )

        servers = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "count": len(servers),
            "time_servers": servers,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search NTP time servers: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_ntp_time_server(
    action: str,
    timeserver: Optional[str] = None,
    type: Optional[str] = None,
    prefer: Optional[bool] = None,
    noselect: Optional[bool] = None,
    server_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Add or remove an NTP time server

    Args:
        action: Action to perform ('create' or 'delete')
        timeserver: Time server hostname or IP (required for create, e.g., 'pool.ntp.org')
        type: Server type (used for create, e.g., 'server', 'pool', 'peer')
        prefer: Whether this is a preferred server (used for create)
        noselect: Whether to mark as noselect (used for create)
        server_id: Time server ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not timeserver:
                return {"success": False, "error": "timeserver is required for create action"}

            server_data: Dict = {
                "timeserver": timeserver,
            }
            if type is not None:
                server_data["type"] = type
            if prefer is not None:
                server_data["prefer"] = prefer
            if noselect is not None:
                server_data["noselect"] = noselect

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create(
                "/services/ntp/time_server", server_data, control
            )

            return {
                "success": True,
                "message": f"NTP time server '{timeserver}' added",
                "time_server": result.get("data", result),
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
                    "details": f"Will permanently delete NTP time server {server_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete(
                "/services/ntp/time_server", server_id, control
            )

            return {
                "success": True,
                "message": f"NTP time server {server_id} deleted",
                "server_id": server_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query time servers before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }

    except Exception as e:
        logger.error(f"Failed to manage NTP time server: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Cron Jobs
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_cron_jobs(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "command",
) -> Dict:
    """Search cron jobs with filtering and pagination

    Args:
        search_term: Search in command or who fields (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (command, minute, hour, mday, month, wday, who, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/cron/jobs",
            sort=sort,
            pagination=pagination,
        )

        jobs = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            jobs = [
                j for j in jobs
                if term_lower in j.get("command", "").lower()
                or term_lower in j.get("who", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(jobs),
            "cron_jobs": jobs,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search cron jobs: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_cron_job(
    minute: str,
    hour: str,
    mday: str,
    month: str,
    wday: str,
    who: str,
    command: str,
    apply_immediately: bool = True,
) -> Dict:
    """Create a cron job

    Args:
        minute: Minute field (0-59, or * for every minute)
        hour: Hour field (0-23, or * for every hour)
        mday: Day of month field (1-31, or * for every day)
        month: Month field (1-12, or * for every month)
        wday: Day of week field (0-7, 0 and 7 are Sunday, or * for every day)
        who: User to run the command as (e.g., 'root')
        command: Command to execute
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        job_data: Dict = {
            "minute": minute,
            "hour": hour,
            "mday": mday,
            "month": month,
            "wday": wday,
            "who": who,
            "command": command,
        }

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/services/cron/job", job_data, control)

        return {
            "success": True,
            "message": f"Cron job created: {minute} {hour} {mday} {month} {wday} {who} {command}",
            "cron_job": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create cron job: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_cron_job(
    job_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a cron job by ID. WARNING: This is irreversible.

    Args:
        job_id: Cron job ID (from search_cron_jobs)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/services/cron/job", job_id, control)

        return {
            "success": True,
            "message": f"Cron job {job_id} deleted",
            "job_id": job_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query cron jobs before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete cron job: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Service Watchdogs
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_service_watchdogs(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search service watchdogs with pagination

    Args:
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, description, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/service_watchdogs",
            sort=sort,
            pagination=pagination,
        )

        watchdogs = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "count": len(watchdogs),
            "service_watchdogs": watchdogs,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search service watchdogs: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_service_watchdog(
    action: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    watchdog_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Add or remove a service watchdog entry

    Args:
        action: Action to perform ('create' or 'delete')
        name: Service name to watch (required for create)
        description: Optional description (used for create)
        watchdog_id: Watchdog ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not name:
                return {"success": False, "error": "name is required for create action"}

            watchdog_data: Dict = {
                "name": name,
            }
            if description is not None:
                watchdog_data["description"] = sanitize_description(description)

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create(
                "/services/service_watchdog", watchdog_data, control
            )

            return {
                "success": True,
                "message": f"Service watchdog '{name}' created",
                "service_watchdog": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if watchdog_id is None:
                return {"success": False, "error": "watchdog_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete service watchdog {watchdog_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete(
                "/services/service_watchdog", watchdog_id, control
            )

            return {
                "success": True,
                "message": f"Service watchdog {watchdog_id} deleted",
                "watchdog_id": watchdog_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query service watchdogs before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }

    except Exception as e:
        logger.error(f"Failed to manage service watchdog: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# SSH
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_ssh_settings() -> Dict:
    """Get the SSH service settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/services/ssh")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get SSH settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_ssh_settings(
    enable: Optional[bool] = None,
    port: Optional[int] = None,
    sshdkeyonly: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the SSH service settings

    Args:
        enable: Whether to enable the SSH service
        port: SSH listening port
        sshdkeyonly: SSH key-only authentication mode ('disabled', 'enabled', 'both')
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if enable is not None:
            updates["enable"] = enable
        if port is not None:
            if port < 1 or port > 65535:
                return {"success": False, "error": "port must be between 1 and 65535"}
            updates["port"] = port
        if sshdkeyonly is not None:
            updates["sshdkeyonly"] = sshdkeyonly

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/services/ssh", updates, control)

        return {
            "success": True,
            "message": "SSH settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update SSH settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Wake on LAN
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def send_wake_on_lan(
    interface: str,
    mac: str,
) -> Dict:
    """Send a Wake-on-LAN magic packet

    Args:
        interface: Interface to send the WoL packet from (e.g., 'lan', 'opt1')
        mac: MAC address of the target device (e.g., 'AA:BB:CC:DD:EE:FF')
    """
    client = get_api_client()
    try:
        normalized_mac = normalize_mac_address(mac)

        wol_data: Dict = {
            "interface": interface,
            "mac": normalized_mac,
        }

        result = await client.crud_create("/services/wake_on_lan/send", wol_data)

        return {
            "success": True,
            "message": f"Wake-on-LAN packet sent to {normalized_mac} on {interface}",
            "interface": interface,
            "mac": normalized_mac,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Failed to send Wake-on-LAN: {e}")
        return {"success": False, "error": str(e)}
