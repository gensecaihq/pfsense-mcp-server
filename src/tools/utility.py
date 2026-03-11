"""Utility tools for pfSense MCP server."""

import os
from datetime import datetime
from typing import Dict

from ..models import PaginationOptions, QueryFilter, SortOptions
from ..server import get_api_client, logger, mcp


@mcp.tool()
async def follow_api_link(link_url: str) -> Dict:
    """Follow a HATEOAS link from a previous API response

    Args:
        link_url: The link URL to follow (from _links section)
    """
    client = get_api_client()
    try:
        result = await client.follow_link(link_url)

        return {
            "success": True,
            "followed_link": link_url,
            "data": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to follow link: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def enable_hateoas() -> Dict:
    """Enable HATEOAS links in API responses for this session"""
    client = get_api_client()
    result = await client.enable_hateoas()
    return {
        "success": True,
        "message": "HATEOAS enabled - API responses will now include navigation links",
        "result": result,
        "timestamp": datetime.utcnow().isoformat()
    }


@mcp.tool()
async def disable_hateoas() -> Dict:
    """Disable HATEOAS links in API responses for this session"""
    client = get_api_client()
    result = await client.disable_hateoas()
    return {
        "success": True,
        "message": "HATEOAS disabled - API responses will be more compact",
        "result": result,
        "timestamp": datetime.utcnow().isoformat()
    }


@mcp.tool()
async def refresh_object_ids(endpoint: str) -> Dict:
    """Refresh object IDs by re-querying an endpoint (handles ID changes after deletions)

    Args:
        endpoint: Relative API path without the /api/v2 prefix (e.g. "/firewall/rule", "/firewall/aliases")
    """
    client = get_api_client()
    try:
        result = await client.refresh_object_ids(endpoint)

        return {
            "success": True,
            "endpoint": endpoint,
            "refreshed_count": len(result.get("data", [])),
            "objects": result.get("data", []),
            "message": "Object IDs refreshed - use updated IDs for future operations",
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to refresh object IDs: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def find_object_by_field(
    endpoint: str,
    field: str,
    value: str
) -> Dict:
    """Find an object by a specific field value (safer than using IDs)

    Args:
        endpoint: Relative API path without the /api/v2 prefix (e.g. "/services/dhcp_server", "/firewall/rules", "/firewall/aliases")
        field: Field name to search by
        value: Value to search for
    """
    client = get_api_client()
    try:
        obj = await client.find_object_by_field(endpoint, field, value)

        if obj:
            return {
                "success": True,
                "endpoint": endpoint,
                "search_field": field,
                "search_value": value,
                "found": True,
                "object": obj,
                "object_id": obj.get("id"),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "success": True,
                "endpoint": endpoint,
                "search_field": field,
                "search_value": value,
                "found": False,
                "message": "No object found matching criteria",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to find object by field: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_api_capabilities() -> Dict:
    """Get comprehensive API capabilities and configuration"""
    client = get_api_client()
    try:
        capabilities = await client.get_api_capabilities()

        return {
            "success": True,
            "api_version": "v2",
            "package": "jaredhendrickson13/pfsense-api",
            "pfsense_version": os.getenv("PFSENSE_VERSION", "CE_2_8_0"),
            "capabilities": capabilities.get("data", capabilities),
            "features": {
                "object_ids": "Dynamic, non-persistent",
                "queries_filters": "Full support with multiple operators",
                "sorting": "Multi-field sorting supported",
                "pagination": "Limit/offset based",
                "hateoas": f"{'Enabled' if client.hateoas_enabled else 'Disabled'}",
                "control_parameters": "Apply, async, placement, append, remove"
            },
            "links": client.extract_links(capabilities),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get API capabilities: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def test_enhanced_connection() -> Dict:
    """Test enhanced API connection with feature validation"""
    client = get_api_client()
    try:
        # Test basic connection
        connected = await client.test_connection()

        if not connected:
            return {
                "success": False,
                "message": "Basic connection failed",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Test advanced features
        tests = []

        # Test filtering
        try:
            await client.get_interfaces(
                filters=[QueryFilter("status", "up")],
                pagination=PaginationOptions(limit=1)
            )
            tests.append({"feature": "filtering", "status": "working"})
        except Exception as e:
            tests.append({"feature": "filtering", "status": "failed", "error": str(e)})

        # Test sorting
        try:
            await client.get_firewall_rules(
                sort=SortOptions(sort_by="interface"),
                pagination=PaginationOptions(limit=1)
            )
            tests.append({"feature": "sorting", "status": "working"})
        except Exception as e:
            tests.append({"feature": "sorting", "status": "failed", "error": str(e)})

        # Test HATEOAS if enabled
        if client.hateoas_enabled:
            try:
                result = await client.get_system_status()
                links = client.extract_links(result)
                if links:
                    tests.append({"feature": "hateoas", "status": "working", "links_found": len(links)})
                else:
                    tests.append({"feature": "hateoas", "status": "no_links"})
            except Exception as e:
                tests.append({"feature": "hateoas", "status": "failed", "error": str(e)})

        working_features = len([t for t in tests if t["status"] == "working"])

        return {
            "success": True,
            "message": f"Enhanced connection test completed - {working_features}/{len(tests)} features working",
            "basic_connection": True,
            "feature_tests": tests,
            "hateoas_enabled": client.hateoas_enabled,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Enhanced connection test failed: {e}")
        return {"success": False, "error": str(e)}
