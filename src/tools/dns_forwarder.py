"""DNS Forwarder (dnsmasq) tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_dns_forwarder_settings() -> Dict:
    """Get the DNS Forwarder (dnsmasq) service settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/services/dns_forwarder/settings")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get DNS forwarder settings: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Host Overrides
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_dns_forwarder_host_overrides(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "host",
) -> Dict:
    """Search DNS Forwarder host overrides with filtering and pagination

    Args:
        search_term: Search in host, domain, IP, or description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (host, domain, ip, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/dns_forwarder/host_overrides",
            sort=sort,
            pagination=pagination,
        )

        overrides = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            overrides = [
                o for o in overrides
                if term_lower in o.get("host", "").lower()
                or term_lower in o.get("domain", "").lower()
                or term_lower in o.get("ip", "").lower()
                or term_lower in o.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(overrides),
            "host_overrides": overrides,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search DNS forwarder host overrides: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_dns_forwarder_host_override(
    host: str,
    domain: str,
    ip: str,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a DNS Forwarder host override entry

    Args:
        host: Hostname (e.g., 'myserver')
        domain: Domain name (e.g., 'example.com')
        ip: IP address to resolve to
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        override_data: Dict = {
            "host": host,
            "domain": domain,
            "ip": ip,
        }

        if descr:
            override_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(
            "/services/dns_forwarder/host_override", override_data, control
        )

        return {
            "success": True,
            "message": f"Host override created: {host}.{domain} -> {ip}",
            "host_override": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create DNS forwarder host override: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_dns_forwarder_host_override(
    override_id: int,
    host: Optional[str] = None,
    domain: Optional[str] = None,
    ip: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing DNS Forwarder host override by ID

    Args:
        override_id: Host override ID (from search_dns_forwarder_host_overrides)
        host: Hostname
        domain: Domain name
        ip: IP address to resolve to
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if host is not None:
            updates["host"] = host
        if domain is not None:
            updates["domain"] = domain
        if ip is not None:
            updates["ip"] = ip
        if descr is not None:
            updates["descr"] = sanitize_description(descr)

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(
            "/services/dns_forwarder/host_override", override_id, updates, control
        )

        return {
            "success": True,
            "message": f"Host override {override_id} updated",
            "override_id": override_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DNS forwarder host override: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_dns_forwarder_host_override(
    override_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a DNS Forwarder host override by ID. WARNING: This is irreversible.

    Args:
        override_id: Host override ID (from search_dns_forwarder_host_overrides)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(
            "/services/dns_forwarder/host_override", override_id, control
        )

        return {
            "success": True,
            "message": f"Host override {override_id} deleted",
            "override_id": override_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query host overrides before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete DNS forwarder host override: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Host Override Aliases
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_dns_forwarder_host_override_aliases(
    parent_id: int,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "host",
) -> Dict:
    """Search aliases for a DNS Forwarder host override

    Args:
        parent_id: Parent host override ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (host, domain, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = [QueryFilter("parent_id", parent_id)]
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/dns_forwarder/host_override/aliases",
            filters=filters,
            sort=sort,
            pagination=pagination,
        )

        aliases = result.get("data") or []

        return {
            "success": True,
            "parent_id": parent_id,
            "page": page,
            "page_size": page_size,
            "count": len(aliases),
            "aliases": aliases,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search DNS forwarder host override aliases: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_dns_forwarder_host_override_alias(
    action: str,
    parent_id: int,
    host: Optional[str] = None,
    domain: Optional[str] = None,
    descr: Optional[str] = None,
    alias_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Add or remove an alias for a DNS Forwarder host override

    Args:
        action: Action to perform ('create' or 'delete')
        parent_id: Parent host override ID
        host: Alias hostname (required for create)
        domain: Alias domain name (required for create)
        descr: Optional description (used for create)
        alias_id: Alias ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not host:
                return {"success": False, "error": "host is required for create action"}
            if not domain:
                return {"success": False, "error": "domain is required for create action"}

            alias_data: Dict = {
                "parent_id": parent_id,
                "host": host,
                "domain": domain,
            }
            if descr is not None:
                alias_data["descr"] = sanitize_description(descr)

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create(
                "/services/dns_forwarder/host_override/alias", alias_data, control
            )

            return {
                "success": True,
                "message": f"Alias '{host}.{domain}' added to host override {parent_id}",
                "alias": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if alias_id is None:
                return {"success": False, "error": "alias_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete alias {alias_id} from host override {parent_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete(
                "/services/dns_forwarder/host_override/alias",
                alias_id,
                control,
                extra_data={"parent_id": parent_id},
            )

            return {
                "success": True,
                "message": f"Alias {alias_id} removed from host override {parent_id}",
                "alias_id": alias_id,
                "parent_id": parent_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query aliases before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }

    except Exception as e:
        logger.error(f"Failed to manage DNS forwarder host override alias: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_dns_forwarder_changes() -> Dict:
    """Apply pending DNS Forwarder changes

    Use this after making changes with apply_immediately=False to batch-apply them.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/services/dns_forwarder/apply")

        return {
            "success": True,
            "message": "DNS Forwarder changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply DNS forwarder changes: {e}")
        return {"success": False, "error": str(e)}
