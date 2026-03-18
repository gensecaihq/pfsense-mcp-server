"""Service tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, Optional

from ..server import get_api_client, logger, mcp

_VALID_STATUS_FILTERS = {"running", "stopped"}


@mcp.tool()
async def search_services(
    search_term: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> Dict:
    """Search and filter system services

    Args:
        search_term: Search in service names or descriptions
        status_filter: Filter by status (running, stopped)
    """
    client = get_api_client()
    try:
        if status_filter is not None and status_filter not in _VALID_STATUS_FILTERS:
            return {
                "success": False,
                "error": f"Invalid status_filter '{status_filter}'. Must be 'running' or 'stopped'",
            }

        if status_filter == "running":
            result = await client.find_running_services()
        elif status_filter == "stopped":
            result = await client.find_stopped_services()
        else:
            result = await client.get_services()

        services = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            services = [
                s for s in services
                if term_lower in s.get("name", "").lower()
                or term_lower in s.get("description", "").lower()
            ]

        return {
            "success": True,
            "filters_applied": {
                "search_term": search_term,
                "status_filter": status_filter,
            },
            "count": len(services),
            "services": services,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search services: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def control_service(
    service_name: str,
    action: str
) -> Dict:
    """Start, stop, or restart a system service

    Args:
        service_name: Name of the service (e.g., "dhcpd", "unbound", "ntpd")
        action: Action to perform ("start", "stop", or "restart")
    """
    client = get_api_client()
    try:
        action_lower = action.lower()
        if action_lower == "start":
            result = await client.start_service(service_name)
        elif action_lower == "stop":
            result = await client.stop_service(service_name)
        elif action_lower == "restart":
            result = await client.restart_service(service_name)
        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'start', 'stop', or 'restart'",
            }

        return {
            "success": True,
            "message": f"Service '{service_name}' {action_lower} command sent",
            "service": service_name,
            "action": action_lower,
            "result": result.get("data", result),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to {action} service {service_name}: {e}")
        return {"success": False, "error": str(e)}
