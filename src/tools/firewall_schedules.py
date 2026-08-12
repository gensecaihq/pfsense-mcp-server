"""Firewall schedule tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Firewall Schedules
# ---------------------------------------------------------------------------
from ..guardrails import guarded, rate_limited
from ..helpers import (
    create_default_sort,
    create_search_pagination,
    field_contains,
    sanitize_description,
)
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_firewall_schedules(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search firewall schedules with filtering and pagination

    Args:
        search_term: Search in schedule name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, descr, schedlabel, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_search_pagination(page, page_size, search_term)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/schedules",
            sort=sort,
            pagination=pagination,
        )

        schedules = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            schedules = [
                s for s in schedules
                if field_contains(s, "name", term_lower)
                or field_contains(s, "descr", term_lower)
                or field_contains(s, "schedlabel", term_lower)
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(schedules),
            "schedules": schedules,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search firewall schedules: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_firewall_schedule(
    name: str,
    hour: str,
    position: Optional[List[int]] = None,
    month: Optional[List[int]] = None,
    day: Optional[List[int]] = None,
    rangedescr: Optional[str] = None,
    descr: Optional[str] = None,
    schedlabel: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a firewall schedule with an initial time range.

    The pfSense API requires at least one time range at creation. Use
    create_schedule_time_range to add further ranges afterwards.

    Args:
        name: Schedule name (alphanumeric and underscores only)
        hour: Start/end time for the initial time range in 24-hour format (e.g., "8:00-17:00")
        position: Days of week for a weekly-recurring range (1=Monday ... 7=Sunday, e.g., [1,2,3,4,5]). Required unless month/day are given.
        month: Months (1-12) for specific calendar dates; each entry pairs with the same-index `day` entry
        day: Days of month pairing with `month` (e.g., month=[12], day=[25] for every Dec 25)
        rangedescr: Description for the initial time range
        descr: Optional description
        schedlabel: Optional schedule label
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()

    if not position and not (month and day):
        return {
            "success": False,
            "error": "Provide either `position` (weekdays, 1=Mon..7=Sun) or both `month` and `day` for the initial time range",
        }

    try:
        time_range: Dict = {"hour": hour}
        if position:
            time_range["position"] = position
        if month:
            time_range["month"] = month
        if day:
            time_range["day"] = day
        if rangedescr:
            time_range["rangedescr"] = sanitize_description(rangedescr)

        schedule_data: Dict = {
            "name": name,
            "timerange": [time_range],
        }

        if descr:
            schedule_data["descr"] = sanitize_description(descr)
        if schedlabel:
            schedule_data["schedlabel"] = schedlabel

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/firewall/schedule", schedule_data, control)

        return {
            "success": True,
            "message": f"Firewall schedule '{name}' created",
            "schedule": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create firewall schedule: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_firewall_schedule(
    schedule_id: int,
    name: Optional[str] = None,
    descr: Optional[str] = None,
    schedlabel: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing firewall schedule by ID

    Args:
        schedule_id: Schedule ID (from search_firewall_schedules)
        name: Schedule name
        descr: Description
        schedlabel: Schedule label
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if name is not None:
            updates["name"] = name
        if descr is not None:
            updates["descr"] = sanitize_description(descr)
        if schedlabel is not None:
            updates["schedlabel"] = schedlabel

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/firewall/schedule", schedule_id, updates, control)

        return {
            "success": True,
            "message": f"Firewall schedule {schedule_id} updated",
            "schedule_id": schedule_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update firewall schedule: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_firewall_schedule(
    schedule_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a firewall schedule by ID. WARNING: This is irreversible.

    Args:
        schedule_id: Schedule ID (from search_firewall_schedules)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/firewall/schedule", schedule_id, control)

        return {
            "success": True,
            "message": f"Firewall schedule {schedule_id} deleted",
            "schedule_id": schedule_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query firewall schedules before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete firewall schedule: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Schedule Time Ranges
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_schedule_time_ranges(
    parent_id: int,
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "position",
) -> Dict:
    """Search time ranges within a firewall schedule

    Args:
        parent_id: Parent schedule ID (from search_firewall_schedules)
        search_term: Search in time range description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (position, month, day, hour, rangedescr, etc.)
    """
    client = get_api_client()
    try:
        filters = [QueryFilter("parent_id", parent_id)]

        pagination, page, page_size = create_search_pagination(page, page_size, search_term)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/firewall/schedule/time_ranges",
            filters=filters,
            sort=sort,
            pagination=pagination,
        )

        time_ranges = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            time_ranges = [
                tr for tr in time_ranges
                if field_contains(tr, "rangedescr", term_lower)
            ]

        return {
            "success": True,
            "parent_id": parent_id,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "parent_id": parent_id,
            },
            "count": len(time_ranges),
            "time_ranges": time_ranges,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search schedule time ranges: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_schedule_time_range(
    parent_id: int,
    month: Optional[List[int]] = None,
    day: Optional[List[int]] = None,
    hour: Optional[str] = None,
    rangedescr: Optional[str] = None,
    position: Optional[List[int]] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a time range within a firewall schedule

    Args:
        parent_id: Parent schedule ID (from search_firewall_schedules)
        month: Months (1-12) for specific calendar dates; each entry pairs with the same-index `day` entry
        day: Days of month pairing with `month` (e.g., month=[12], day=[25] for every Dec 25)
        hour: Start/end time in 24-hour format (e.g., "8:00-17:00")
        rangedescr: Description for this time range entry
        position: Days of week for a weekly-recurring range (1=Monday ... 7=Sunday, e.g., [1,2,3,4,5])
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        range_data: Dict = {
            "parent_id": parent_id,
        }

        if month:
            range_data["month"] = month
        if day:
            range_data["day"] = day
        if hour:
            range_data["hour"] = hour
        if rangedescr:
            range_data["rangedescr"] = sanitize_description(rangedescr)
        if position:
            range_data["position"] = position

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/firewall/schedule/time_range", range_data, control)

        return {
            "success": True,
            "message": f"Time range created for schedule {parent_id}",
            "time_range": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create schedule time range: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_schedule_time_range(
    time_range_id: int,
    parent_id: Optional[int] = None,
    month: Optional[List[int]] = None,
    day: Optional[List[int]] = None,
    hour: Optional[str] = None,
    rangedescr: Optional[str] = None,
    position: Optional[List[int]] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing time range within a firewall schedule by ID

    Args:
        time_range_id: Time range ID (from search_schedule_time_ranges)
        parent_id: Parent schedule ID (if moving to a different schedule)
        month: Months (1-12) for specific calendar dates; each entry pairs with the same-index `day` entry
        day: Days of month pairing with `month`
        hour: Start/end time in 24-hour format (e.g., "8:00-17:00")
        rangedescr: Description for this time range entry
        position: Days of week for a weekly-recurring range (1=Monday ... 7=Sunday)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "parent_id": "parent_id",
            "month": "month",
            "day": "day",
            "hour": "hour",
            "rangedescr": "rangedescr",
            "position": "position",
        }

        params = {
            "parent_id": parent_id,
            "month": month,
            "day": day,
            "hour": hour,
            "rangedescr": rangedescr,
            "position": position,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                api_field = field_map[param_name]
                if api_field == "rangedescr" and isinstance(value, str):
                    updates[api_field] = sanitize_description(value)
                else:
                    updates[api_field] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/firewall/schedule/time_range", time_range_id, updates, control)

        return {
            "success": True,
            "message": f"Schedule time range {time_range_id} updated",
            "time_range_id": time_range_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update schedule time range: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_schedule_time_range(
    time_range_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a time range from a firewall schedule by ID. WARNING: This is irreversible.

    Args:
        time_range_id: Time range ID (from search_schedule_time_ranges)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/firewall/schedule/time_range", time_range_id, control)

        return {
            "success": True,
            "message": f"Schedule time range {time_range_id} deleted",
            "time_range_id": time_range_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query schedule time ranges before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete schedule time range: {e}")
        return {"success": False, "error": str(e)}
