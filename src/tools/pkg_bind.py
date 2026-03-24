"""BIND DNS server package tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Zones
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_bind_zones(
    search_term: Optional[str] = None,
    zone_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search BIND DNS zones with filtering and pagination

    Requires the BIND package to be installed on pfSense.

    Args:
        search_term: Search in zone name/description (client-side filter)
        zone_type: Filter by zone type (master, slave, forward)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, type, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if zone_type:
            if zone_type not in ("master", "slave", "forward"):
                return {"success": False, "error": "zone_type must be 'master', 'slave', or 'forward'"}
            filters.append(QueryFilter("type", zone_type))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/bind/zones",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        zones = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            zones = [
                z for z in zones
                if term_lower in z.get("name", "").lower()
                or term_lower in z.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "zone_type": zone_type,
            },
            "count": len(zones),
            "zones": zones,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search BIND zones: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_bind_zone(
    name: str,
    type: str = "master",
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a BIND DNS zone

    Args:
        name: Zone name (domain name, e.g., 'example.com')
        type: Zone type ('master', 'slave', or 'forward')
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    if type not in ("master", "slave", "forward"):
        return {"success": False, "error": "type must be 'master', 'slave', or 'forward'"}

    client = get_api_client()
    try:
        zone_data: Dict = {
            "name": name,
            "type": type,
        }

        if descr:
            zone_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/services/bind/zone", zone_data, control)

        return {
            "success": True,
            "message": f"BIND zone '{name}' created (type={type})",
            "zone": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create BIND zone: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_bind_zone(
    zone_id: int,
    name: Optional[str] = None,
    type: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing BIND DNS zone by ID

    Args:
        zone_id: Zone ID (from search_bind_zones)
        name: Zone name (domain name)
        type: Zone type ('master', 'slave', or 'forward')
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    if type is not None and type not in ("master", "slave", "forward"):
        return {"success": False, "error": "type must be 'master', 'slave', or 'forward'"}

    client = get_api_client()
    try:
        params = {
            "name": name,
            "type": type,
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
        result = await client.crud_update("/services/bind/zone", zone_id, updates, control)

        return {
            "success": True,
            "message": f"BIND zone {zone_id} updated",
            "zone_id": zone_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update BIND zone: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_bind_zone(
    zone_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Delete a BIND DNS zone by ID. WARNING: This is irreversible.

    This will also remove all records within the zone.

    Args:
        zone_id: Zone ID (from search_bind_zones)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will permanently delete BIND zone {zone_id} and all its records.",
        }

    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/services/bind/zone", zone_id, control)

        return {
            "success": True,
            "message": f"BIND zone {zone_id} deleted",
            "zone_id": zone_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query zones before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete BIND zone: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Zone Records
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_bind_zone_records(
    parent_id: int,
    search_term: Optional[str] = None,
    record_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search DNS records within a BIND zone

    Args:
        parent_id: Zone ID to list records for
        search_term: Search in record name/rdata (client-side filter)
        record_type: Filter by record type (A, AAAA, CNAME, MX, TXT, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, type, rdata, etc.)
    """
    client = get_api_client()
    try:
        filters = [QueryFilter("parent_id", str(parent_id))]

        if record_type:
            filters.append(QueryFilter("type", record_type))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/bind/zone/records",
            filters=filters,
            sort=sort,
            pagination=pagination,
        )

        records = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            records = [
                r for r in records
                if term_lower in r.get("name", "").lower()
                or term_lower in r.get("rdata", "").lower()
            ]

        return {
            "success": True,
            "parent_id": parent_id,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "record_type": record_type,
            },
            "count": len(records),
            "records": records,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search BIND zone records: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_bind_zone_record(
    action: str,
    parent_id: int,
    name: Optional[str] = None,
    type: Optional[str] = None,
    rdata: Optional[str] = None,
    record_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Create or delete a DNS record within a BIND zone

    Args:
        action: Action to perform ('create' or 'delete')
        parent_id: Parent zone ID
        name: Record name/hostname (required for create, e.g., 'www', 'mail')
        type: Record type (required for create: A, AAAA, CNAME, MX, TXT, NS, PTR, SRV, etc.)
        rdata: Record data (required for create, e.g., '192.168.1.10' for A record)
        record_id: Record ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not name:
                return {"success": False, "error": "name is required for create action"}
            if not type:
                return {"success": False, "error": "type is required for create action"}
            if not rdata:
                return {"success": False, "error": "rdata is required for create action"}

            record_data: Dict = {
                "parent_id": parent_id,
                "name": name,
                "type": type,
                "rdata": rdata,
            }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create("/services/bind/zone/record", record_data, control)

            return {
                "success": True,
                "message": f"DNS record '{name}' ({type} -> {rdata}) added to zone {parent_id}",
                "record": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if record_id is None:
                return {"success": False, "error": "record_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete DNS record {record_id} from zone {parent_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete(
                "/services/bind/zone/record", record_id, control,
                extra_data={"parent_id": parent_id},
            )

            return {
                "success": True,
                "message": f"DNS record {record_id} removed from zone {parent_id}",
                "record_id": record_id,
                "parent_id": parent_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query records before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }
    except Exception as e:
        logger.error(f"Failed to manage BIND zone record: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_bind_settings() -> Dict:
    """Get the current BIND DNS server settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/services/bind/settings")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get BIND settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_bind_settings(
    enable: Optional[bool] = None,
    listen_on: Optional[str] = None,
    forwarder_ips: Optional[str] = None,
    dnssec_validation: Optional[str] = None,
    log_severity: Optional[str] = None,
    rate_limit: Optional[int] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update BIND DNS server settings

    Args:
        enable: Enable or disable the BIND service
        listen_on: Interfaces/IPs to listen on
        forwarder_ips: Forwarder IP addresses (semicolon-separated)
        dnssec_validation: DNSSEC validation mode (auto, yes, no)
        log_severity: Logging severity level
        rate_limit: Query rate limit
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "enable": enable,
            "listen_on": listen_on,
            "forwarder_ips": forwarder_ips,
            "dnssec_validation": dnssec_validation,
            "log_severity": log_severity,
            "rate_limit": rate_limit,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings("/services/bind/settings", updates, control)

        return {
            "success": True,
            "message": "BIND settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update BIND settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Access Lists
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_bind_access_lists(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search BIND access control lists

    Args:
        search_term: Search in access list name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/bind/access_lists",
            sort=sort,
            pagination=pagination,
        )

        access_lists = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            access_lists = [
                a for a in access_lists
                if term_lower in a.get("name", "").lower()
                or term_lower in a.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(access_lists),
            "access_lists": access_lists,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search BIND access lists: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_bind_access_list(
    action: str,
    name: Optional[str] = None,
    descr: Optional[str] = None,
    entries: Optional[List[str]] = None,
    access_list_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Create or delete a BIND access control list

    Args:
        action: Action to perform ('create' or 'delete')
        name: Access list name (required for create)
        descr: Optional description (used for create)
        entries: List of network entries (used for create, e.g., ['192.168.1.0/24', '10.0.0.0/8'])
        access_list_id: Access list ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not name:
                return {"success": False, "error": "name is required for create action"}

            acl_data: Dict = {"name": name}
            if descr:
                acl_data["descr"] = sanitize_description(descr)
            if entries:
                acl_data["entries"] = entries

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create("/services/bind/access_list", acl_data, control)

            return {
                "success": True,
                "message": f"BIND access list '{name}' created",
                "access_list": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if access_list_id is None:
                return {"success": False, "error": "access_list_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete BIND access list {access_list_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete("/services/bind/access_list", access_list_id, control)

            return {
                "success": True,
                "message": f"BIND access list {access_list_id} deleted",
                "access_list_id": access_list_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query access lists before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }
    except Exception as e:
        logger.error(f"Failed to manage BIND access list: {e}")
        return {"success": False, "error": str(e)}
