"""Traffic shaper tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import create_default_sort, create_pagination, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Traffic Shapers
# ---------------------------------------------------------------------------


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_traffic_shapers(
    search_term: Optional[str] = None,
    interface: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "interface",
) -> Dict:
    """Search traffic shapers with filtering and pagination

    Args:
        search_term: General search across interface/description (client-side filter)
        interface: Filter by interface (wan, lan, opt1, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (interface, scheduler, bandwidth, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if interface:
            filters.append(QueryFilter("interface", interface))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/traffic_shapers",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        shapers = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            shapers = [
                s for s in shapers
                if term_lower in s.get("interface", "").lower()
                or term_lower in s.get("descr", "").lower()
                or term_lower in s.get("scheduler", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "interface": interface,
            },
            "count": len(shapers),
            "traffic_shapers": shapers,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search traffic shapers: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_traffic_shaper(
    interface: str,
    scheduler: str,
    bandwidthtype: str,
    bandwidth: int,
    enabled: bool = True,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a traffic shaper on an interface

    Args:
        interface: Interface to apply shaper to (wan, lan, opt1, etc.)
        scheduler: Scheduler type (HFSC, CBQ, FAIRQ, CODELQ, PRIQ)
        bandwidthtype: Bandwidth unit (Kb, Mb, Gb, b, %)
        bandwidth: Bandwidth value
        enabled: Whether the shaper is enabled
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        shaper_data: Dict[str, Union[str, int, bool]] = {
            "interface": interface,
            "scheduler": scheduler,
            "bandwidthtype": bandwidthtype,
            "bandwidth": bandwidth,
            "enabled": enabled,
        }

        if descr:
            shaper_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/firewall/traffic_shaper", shaper_data, control)

        return {
            "success": True,
            "message": f"Traffic shaper created on {interface} ({scheduler}, {bandwidth}{bandwidthtype})",
            "traffic_shaper": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create traffic shaper: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_traffic_shaper(
    shaper_id: int,
    interface: Optional[str] = None,
    scheduler: Optional[str] = None,
    bandwidthtype: Optional[str] = None,
    bandwidth: Optional[int] = None,
    enabled: Optional[bool] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing traffic shaper by ID

    Args:
        shaper_id: Traffic shaper ID (from search_traffic_shapers)
        interface: Interface to apply shaper to
        scheduler: Scheduler type (HFSC, CBQ, FAIRQ, CODELQ, PRIQ)
        bandwidthtype: Bandwidth unit (Kb, Mb, Gb, b, %)
        bandwidth: Bandwidth value
        enabled: Whether the shaper is enabled
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "interface": interface,
            "scheduler": scheduler,
            "bandwidthtype": bandwidthtype,
            "bandwidth": bandwidth,
            "enabled": enabled,
            "descr": descr,
        }

        updates: Dict[str, Union[str, int, bool]] = {}
        for param_name, value in params.items():
            if value is not None:
                if param_name == "descr" and isinstance(value, str):
                    updates[param_name] = sanitize_description(value)
                else:
                    updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/firewall/traffic_shaper", shaper_id, updates, control)

        return {
            "success": True,
            "message": f"Traffic shaper {shaper_id} updated",
            "shaper_id": shaper_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update traffic shaper: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_traffic_shaper(
    shaper_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a traffic shaper by ID. WARNING: This is irreversible.

    Args:
        shaper_id: Traffic shaper ID (from search_traffic_shapers)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/firewall/traffic_shaper", shaper_id, control)

        return {
            "success": True,
            "message": f"Traffic shaper {shaper_id} deleted",
            "shaper_id": shaper_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query traffic shapers before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete traffic shaper: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Shaper Queues
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_shaper_queues(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search traffic shaper queues with filtering and pagination

    Args:
        search_term: General search across queue name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, priority, bandwidth, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/traffic_shaper/queues",
            sort=sort,
            pagination=pagination,
        )

        queues = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            queues = [
                q for q in queues
                if term_lower in q.get("name", "").lower()
                or term_lower in q.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(queues),
            "shaper_queues": queues,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search shaper queues: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_shaper_queue(
    parent_id: int,
    name: str,
    priority: Optional[int] = None,
    qlimit: Optional[int] = None,
    bandwidthtype: Optional[str] = None,
    bandwidth: Optional[int] = None,
    enabled: bool = True,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a traffic shaper queue

    Args:
        parent_id: Parent shaper ID to attach the queue to
        name: Queue name
        priority: Queue priority (0-15, higher = more priority)
        qlimit: Queue limit (packet count)
        bandwidthtype: Bandwidth unit (Kb, Mb, Gb, b, %)
        bandwidth: Bandwidth value
        enabled: Whether the queue is enabled
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        queue_data: Dict[str, Union[str, int, bool]] = {
            "parent_id": parent_id,
            "name": name,
            "enabled": enabled,
        }

        if priority is not None:
            queue_data["priority"] = priority
        if qlimit is not None:
            queue_data["qlimit"] = qlimit
        if bandwidthtype:
            queue_data["bandwidthtype"] = bandwidthtype
        if bandwidth is not None:
            queue_data["bandwidth"] = bandwidth
        if descr:
            queue_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/firewall/traffic_shaper/queue", queue_data, control)

        return {
            "success": True,
            "message": f"Shaper queue '{name}' created under parent {parent_id}",
            "shaper_queue": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create shaper queue: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_shaper_queue(
    queue_id: int,
    name: Optional[str] = None,
    priority: Optional[int] = None,
    qlimit: Optional[int] = None,
    bandwidthtype: Optional[str] = None,
    bandwidth: Optional[int] = None,
    enabled: Optional[bool] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing shaper queue by ID

    Args:
        queue_id: Shaper queue ID (from search_shaper_queues)
        name: Queue name
        priority: Queue priority (0-15)
        qlimit: Queue limit (packet count)
        bandwidthtype: Bandwidth unit (Kb, Mb, Gb, b, %)
        bandwidth: Bandwidth value
        enabled: Whether the queue is enabled
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "name": name,
            "priority": priority,
            "qlimit": qlimit,
            "bandwidthtype": bandwidthtype,
            "bandwidth": bandwidth,
            "enabled": enabled,
            "descr": descr,
        }

        updates: Dict[str, Union[str, int, bool]] = {}
        for param_name, value in params.items():
            if value is not None:
                if param_name == "descr" and isinstance(value, str):
                    updates[param_name] = sanitize_description(value)
                else:
                    updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/firewall/traffic_shaper/queue", queue_id, updates, control)

        return {
            "success": True,
            "message": f"Shaper queue {queue_id} updated",
            "queue_id": queue_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update shaper queue: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_shaper_queue(
    queue_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a shaper queue by ID. WARNING: This is irreversible.

    Args:
        queue_id: Shaper queue ID (from search_shaper_queues)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/firewall/traffic_shaper/queue", queue_id, control)

        return {
            "success": True,
            "message": f"Shaper queue {queue_id} deleted",
            "queue_id": queue_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query shaper queues before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete shaper queue: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Traffic Limiters
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_traffic_limiters(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search traffic limiters (dummynet pipes) with filtering and pagination

    Args:
        search_term: General search across limiter name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, bandwidth, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/traffic_shaper/limiters",
            sort=sort,
            pagination=pagination,
        )

        limiters = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            limiters = [
                l for l in limiters
                if term_lower in l.get("name", "").lower()
                or term_lower in l.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(limiters),
            "traffic_limiters": limiters,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search traffic limiters: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_traffic_limiter(
    name: str,
    bandwidth: int,
    bandwidthtype: str,
    mask: Optional[str] = None,
    maskbits: Optional[int] = None,
    descr: Optional[str] = None,
    enabled: bool = True,
    apply_immediately: bool = True,
) -> Dict:
    """Create a traffic limiter (dummynet pipe)

    Args:
        name: Limiter name
        bandwidth: Bandwidth value
        bandwidthtype: Bandwidth unit (Kb, Mb, Gb, b)
        mask: Mask type (none, srcaddress, dstaddress)
        maskbits: Mask bits for per-host limiting
        descr: Optional description
        enabled: Whether the limiter is enabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        limiter_data: Dict[str, Union[str, int, bool]] = {
            "name": name,
            "bandwidth": bandwidth,
            "bandwidthtype": bandwidthtype,
            "enabled": enabled,
        }

        if mask:
            limiter_data["mask"] = mask
        if maskbits is not None:
            limiter_data["maskbits"] = maskbits
        if descr:
            limiter_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/firewall/traffic_shaper/limiter", limiter_data, control)

        return {
            "success": True,
            "message": f"Traffic limiter '{name}' created ({bandwidth}{bandwidthtype})",
            "traffic_limiter": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create traffic limiter: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_traffic_limiter(
    limiter_id: int,
    name: Optional[str] = None,
    bandwidth: Optional[int] = None,
    bandwidthtype: Optional[str] = None,
    mask: Optional[str] = None,
    maskbits: Optional[int] = None,
    descr: Optional[str] = None,
    enabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing traffic limiter by ID

    Args:
        limiter_id: Traffic limiter ID (from search_traffic_limiters)
        name: Limiter name
        bandwidth: Bandwidth value
        bandwidthtype: Bandwidth unit (Kb, Mb, Gb, b)
        mask: Mask type (none, srcaddress, dstaddress)
        maskbits: Mask bits for per-host limiting
        descr: Description
        enabled: Whether the limiter is enabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "name": name,
            "bandwidth": bandwidth,
            "bandwidthtype": bandwidthtype,
            "mask": mask,
            "maskbits": maskbits,
            "descr": descr,
            "enabled": enabled,
        }

        updates: Dict[str, Union[str, int, bool]] = {}
        for param_name, value in params.items():
            if value is not None:
                if param_name == "descr" and isinstance(value, str):
                    updates[param_name] = sanitize_description(value)
                else:
                    updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/firewall/traffic_shaper/limiter", limiter_id, updates, control)

        return {
            "success": True,
            "message": f"Traffic limiter {limiter_id} updated",
            "limiter_id": limiter_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update traffic limiter: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_traffic_limiter(
    limiter_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a traffic limiter by ID. WARNING: This is irreversible.

    Args:
        limiter_id: Traffic limiter ID (from search_traffic_limiters)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/firewall/traffic_shaper/limiter", limiter_id, control)

        return {
            "success": True,
            "message": f"Traffic limiter {limiter_id} deleted",
            "limiter_id": limiter_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query traffic limiters before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete traffic limiter: {e}")
        return {"success": False, "error": str(e)}
