"""System settings tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import create_default_sort, create_pagination, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# DNS
# ---------------------------------------------------------------------------


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_system_dns() -> Dict:
    """Get the current system DNS server configuration"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/system/dns")

        return {
            "success": True,
            "dns": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get system DNS: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_system_dns(
    dnsserver: Optional[List[str]] = None,
    dnslocalhost: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update system DNS server settings

    Args:
        dnsserver: Array of DNS server IP addresses (e.g., ["8.8.8.8", "1.1.1.1"])
        dnslocalhost: Whether to use the local DNS resolver (Unbound) as the primary DNS
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict[str, Union[List, bool]] = {}

        if dnsserver is not None:
            updates["dnsserver"] = dnsserver
        if dnslocalhost is not None:
            updates["dnslocalhost"] = dnslocalhost

        if not updates:
            return {"success": False, "error": "No fields to update - provide dnsserver and/or dnslocalhost"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/system/dns", updates, control)

        return {
            "success": True,
            "message": "System DNS settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update system DNS: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Hostname
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_system_hostname() -> Dict:
    """Get the current system hostname and domain"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/system/hostname")

        return {
            "success": True,
            "hostname": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get system hostname: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_system_hostname(
    hostname: Optional[str] = None,
    domain: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update the system hostname and/or domain

    Args:
        hostname: System hostname (e.g., "pfsense", "fw01")
        domain: System domain (e.g., "localdomain", "example.com")
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict[str, str] = {}

        if hostname is not None:
            updates["hostname"] = hostname
        if domain is not None:
            updates["domain"] = domain

        if not updates:
            return {"success": False, "error": "No fields to update - provide hostname and/or domain"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/system/hostname", updates, control)

        return {
            "success": True,
            "message": "System hostname updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update system hostname: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_system_tunables(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "tunable",
) -> Dict:
    """Search system tunables (sysctl values) with filtering and pagination

    Args:
        search_term: General search across tunable name/value/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (tunable, value, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/system/tunables",
            sort=sort,
            pagination=pagination,
        )

        tunables = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            tunables = [
                t for t in tunables
                if term_lower in t.get("tunable", "").lower()
                or term_lower in str(t.get("value", "")).lower()
                or term_lower in t.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(tunables),
            "tunables": tunables,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search system tunables: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_system_tunable(
    tunable: str,
    value: str,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a system tunable (sysctl value)

    Args:
        tunable: Tunable name (e.g., "net.inet.ip.forwarding")
        value: Tunable value
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        tunable_data: Dict[str, str] = {
            "tunable": tunable,
            "value": value,
        }

        if descr:
            tunable_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/system/tunable", tunable_data, control)

        return {
            "success": True,
            "message": f"System tunable '{tunable}' created with value '{value}'",
            "tunable": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create system tunable: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_system_tunable(
    tunable_id: int,
    tunable: Optional[str] = None,
    value: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing system tunable by ID

    Args:
        tunable_id: Tunable ID (from search_system_tunables)
        tunable: Tunable name
        value: Tunable value
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "tunable": tunable,
            "value": value,
            "descr": descr,
        }

        updates: Dict[str, str] = {}
        for param_name, val in params.items():
            if val is not None:
                if param_name == "descr":
                    updates[param_name] = sanitize_description(val)
                else:
                    updates[param_name] = val

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/system/tunable", tunable_id, updates, control)

        return {
            "success": True,
            "message": f"System tunable {tunable_id} updated",
            "tunable_id": tunable_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update system tunable: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_system_tunable(
    tunable_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a system tunable by ID. WARNING: This is irreversible.

    Args:
        tunable_id: Tunable ID (from search_system_tunables)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/system/tunable", tunable_id, control)

        return {
            "success": True,
            "message": f"System tunable {tunable_id} deleted",
            "tunable_id": tunable_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query tunables before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete system tunable: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# System Version
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_system_version() -> Dict:
    """Get the pfSense system version information"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/system/version")

        return {
            "success": True,
            "version": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get system version: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# CARP Status
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_carp_status() -> Dict:
    """Get the current CARP (Common Address Redundancy Protocol) status"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/status/carp")

        return {
            "success": True,
            "carp_status": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get CARP status: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_carp_maintenance(
    enable: Optional[bool] = None,
    maintenance_mode: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update CARP maintenance mode settings

    Args:
        enable: Enable or disable CARP globally
        maintenance_mode: Enable or disable CARP maintenance mode (sets all VIPs to backup)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict[str, bool] = {}

        if enable is not None:
            updates["enable"] = enable
        if maintenance_mode is not None:
            updates["maintenance_mode"] = maintenance_mode

        if not updates:
            return {"success": False, "error": "No fields to update - provide enable and/or maintenance_mode"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/status/carp", updates, control)

        return {
            "success": True,
            "message": "CARP settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update CARP maintenance: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Installed Packages
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_installed_packages(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search installed packages with filtering and pagination

    Args:
        search_term: General search across package name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, version, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/system/packages",
            sort=sort,
            pagination=pagination,
        )

        packages = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            packages = [
                p for p in packages
                if term_lower in p.get("name", "").lower()
                or term_lower in p.get("descr", "").lower()
                or term_lower in p.get("version", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(packages),
            "packages": packages,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search installed packages: {e}")
        return {"success": False, "error": str(e)}
