"""DNS Resolver (Unbound) tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import (
    create_default_sort,
    create_pagination,
    sanitize_description,
    validate_fqdn,
)
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations

# API endpoint constants (pfSense REST API v2 paths, without /api/v2 prefix)
from ..guardrails import guarded
_SETTINGS = "/services/dns_resolver/settings"
_HOST_OVERRIDES = "/services/dns_resolver/host_overrides"
_HOST_OVERRIDE = "/services/dns_resolver/host_override"
_HOST_OVERRIDE_ALIASES = "/services/dns_resolver/host_override/aliases"
_DOMAIN_OVERRIDES = "/services/dns_resolver/domain_overrides"
_DOMAIN_OVERRIDE = "/services/dns_resolver/domain_override"
_ACCESS_LISTS = "/services/dns_resolver/access_lists"
_ACCESS_LIST = "/services/dns_resolver/access_list"
_APPLY = "/services/dns_resolver/apply"


# --- Settings tools ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_dns_resolver_settings() -> Dict:
    """Get the current DNS Resolver (Unbound) settings

    Returns the full Unbound configuration including enable state,
    DNSSEC, forwarding mode, DHCP registration, and custom options.
    """
    client = get_api_client()
    try:
        result = await client.crud_get_settings(_SETTINGS)

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get DNS Resolver settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_dns_resolver_settings(
    enable: Optional[bool] = None,
    dnssec: Optional[bool] = None,
    forwarding: Optional[bool] = None,
    register_dhcp: Optional[bool] = None,
    register_dhcp_static: Optional[bool] = None,
    custom_options: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update DNS Resolver (Unbound) settings

    Args:
        enable: Enable or disable the DNS Resolver service
        dnssec: Enable or disable DNSSEC validation
        forwarding: Enable or disable forwarding mode (forward queries to upstream DNS)
        register_dhcp: Register DHCP leases in the DNS Resolver
        register_dhcp_static: Register DHCP static mappings in the DNS Resolver
        custom_options: Custom Unbound configuration options (advanced)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "enable": "enable",
            "dnssec": "dnssec",
            "forwarding": "forwarding",
            "register_dhcp": "register_dhcp",
            "register_dhcp_static": "register_dhcp_static",
            "custom_options": "custom_options",
        }

        params = {
            "enable": enable,
            "dnssec": dnssec,
            "forwarding": forwarding,
            "register_dhcp": register_dhcp,
            "register_dhcp_static": register_dhcp_static,
            "custom_options": custom_options,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update_settings(_SETTINGS, updates, control)

        return {
            "success": True,
            "message": "DNS Resolver settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DNS Resolver settings: {e}")
        return {"success": False, "error": str(e)}


# --- Host Override tools ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_dns_host_overrides(
    search_term: Optional[str] = None,
    domain: Optional[str] = None,
    host: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "host",
) -> Dict:
    """Search DNS host overrides with filtering and pagination

    Args:
        search_term: General search across host, domain, and description fields (client-side filter)
        domain: Filter by domain name
        host: Filter by hostname
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (host, domain, ip, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if domain:
            filters.append(QueryFilter("domain", domain))

        if host:
            filters.append(QueryFilter("host", host))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            _HOST_OVERRIDES,
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        overrides = result.get("data") or []

        # Client-side filtering for general search term
        if search_term:
            term_lower = search_term.lower()
            overrides = [
                o for o in overrides
                if term_lower in o.get("host", "").lower()
                or term_lower in o.get("domain", "").lower()
                or term_lower in o.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "domain": domain,
                "host": host,
            },
            "count": len(overrides),
            "host_overrides": overrides,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search DNS host overrides: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_dns_host_override(
    host: str,
    domain: str,
    ip: List[str],
    descr: Optional[str] = None,
    aliases: Optional[List[Dict]] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a DNS host override entry

    Args:
        host: Hostname (e.g., "server1")
        domain: Domain name (e.g., "example.com")
        ip: List of IP addresses to resolve to (e.g., ["192.168.1.10"])
        descr: Optional description
        aliases: Optional list of alias dicts, each with "host" and "domain" keys
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        override_data = {
            "host": host,
            "domain": domain,
            "ip": ip,
        }

        if descr:
            override_data["descr"] = sanitize_description(descr)

        if aliases:
            override_data["aliases"] = aliases

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(_HOST_OVERRIDE, override_data, control)

        return {
            "success": True,
            "message": f"DNS host override created: {host}.{domain} -> {', '.join(ip)}",
            "host_override": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create DNS host override: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_dns_host_override(
    override_id: int,
    host: Optional[str] = None,
    domain: Optional[str] = None,
    ip: Optional[List[str]] = None,
    descr: Optional[str] = None,
    aliases: Optional[List[Dict]] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing DNS host override by ID

    Args:
        override_id: Host override ID (from search_dns_host_overrides)
        host: New hostname
        domain: New domain name
        ip: New list of IP addresses
        descr: New description
        aliases: New list of alias dicts, each with "host" and "domain" keys
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "host": "host",
            "domain": "domain",
            "ip": "ip",
            "descr": "descr",
            "aliases": "aliases",
        }

        params = {
            "host": host,
            "domain": domain,
            "ip": ip,
            "descr": descr,
            "aliases": aliases,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        if "descr" in updates:
            updates["descr"] = sanitize_description(updates["descr"])

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(_HOST_OVERRIDE, override_id, updates, control)

        return {
            "success": True,
            "message": f"DNS host override {override_id} updated",
            "override_id": override_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DNS host override: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_dns_host_override(
    override_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a DNS host override by ID. WARNING: This is irreversible.

    Args:
        override_id: Host override ID (from search_dns_host_overrides)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(_HOST_OVERRIDE, override_id, control)

        return {
            "success": True,
            "message": f"DNS host override {override_id} deleted",
            "override_id": override_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query host overrides before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete DNS host override: {e}")
        return {"success": False, "error": str(e)}


# --- Host Override Aliases tool ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_dns_host_override_aliases(
    parent_id: int,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "host",
) -> Dict:
    """Search aliases for a specific DNS host override

    Args:
        parent_id: The host override ID to list aliases for
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (host, domain, etc.)
    """
    client = get_api_client()
    try:
        filters = [QueryFilter("parent_id", str(parent_id))]

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            _HOST_OVERRIDE_ALIASES,
            filters=filters,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "parent_id": parent_id,
            "count": len(result.get("data") or []),
            "aliases": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search DNS host override aliases: {e}")
        return {"success": False, "error": str(e)}


# --- Domain Override tools ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_dns_domain_overrides(
    domain: Optional[str] = None,
    ip: Optional[str] = None,
    descr: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "domain",
) -> Dict:
    """Search DNS domain overrides with filtering and pagination

    Args:
        domain: Filter by domain name
        ip: Filter by forwarding IP address
        descr: Filter by description (partial match)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (domain, ip, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if domain:
            filters.append(QueryFilter("domain", domain))

        if ip:
            filters.append(QueryFilter("ip", ip))

        if descr:
            filters.append(QueryFilter("descr", descr, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            _DOMAIN_OVERRIDES,
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "domain": domain,
                "ip": ip,
                "descr": descr,
            },
            "count": len(result.get("data") or []),
            "domain_overrides": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search DNS domain overrides: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_dns_domain_override(
    domain: str,
    ip: str,
    descr: Optional[str] = None,
    forward_tls_upstream: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a DNS domain override entry

    Args:
        domain: Domain name to override (e.g., "example.com")
        ip: IP address of the authoritative DNS server for this domain
        descr: Optional description
        forward_tls_upstream: Whether to use TLS for forwarding to this upstream
        apply_immediately: Whether to apply changes immediately
    """
    # Validate domain format
    domain_error = validate_fqdn(domain)
    if domain_error:
        return {"success": False, "error": domain_error}

    client = get_api_client()
    try:
        override_data = {
            "domain": domain,
            "ip": ip,
        }

        if descr:
            override_data["descr"] = sanitize_description(descr)

        if forward_tls_upstream is not None:
            override_data["forward_tls_upstream"] = forward_tls_upstream

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(_DOMAIN_OVERRIDE, override_data, control)

        return {
            "success": True,
            "message": f"DNS domain override created: {domain} -> {ip}",
            "domain_override": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create DNS domain override: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_dns_domain_override(
    override_id: int,
    domain: Optional[str] = None,
    ip: Optional[str] = None,
    descr: Optional[str] = None,
    forward_tls_upstream: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing DNS domain override by ID

    Args:
        override_id: Domain override ID (from search_dns_domain_overrides)
        domain: New domain name
        ip: New forwarding IP address
        descr: New description
        forward_tls_upstream: Whether to use TLS for forwarding to this upstream
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "domain": "domain",
            "ip": "ip",
            "descr": "descr",
            "forward_tls_upstream": "forward_tls_upstream",
        }

        params = {
            "domain": domain,
            "ip": ip,
            "descr": descr,
            "forward_tls_upstream": forward_tls_upstream,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        # Validate domain if provided
        if "domain" in updates:
            domain_error = validate_fqdn(updates["domain"])
            if domain_error:
                return {"success": False, "error": domain_error}

        if "descr" in updates:
            updates["descr"] = sanitize_description(updates["descr"])

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(_DOMAIN_OVERRIDE, override_id, updates, control)

        return {
            "success": True,
            "message": f"DNS domain override {override_id} updated",
            "override_id": override_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DNS domain override: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_dns_domain_override(
    override_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a DNS domain override by ID. WARNING: This is irreversible.

    Args:
        override_id: Domain override ID (from search_dns_domain_overrides)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(_DOMAIN_OVERRIDE, override_id, control)

        return {
            "success": True,
            "message": f"DNS domain override {override_id} deleted",
            "override_id": override_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query domain overrides before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete DNS domain override: {e}")
        return {"success": False, "error": str(e)}


# --- Access List tools ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_dns_access_lists(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "aclname",
) -> Dict:
    """Search DNS Resolver access lists with pagination

    Args:
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (aclname, aclaction, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            _ACCESS_LISTS,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "count": len(result.get("data") or []),
            "access_lists": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search DNS access lists: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_dns_access_list(
    aclname: str,
    aclaction: str,
    descr: Optional[str] = None,
    networks: Optional[List[Dict]] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a DNS Resolver access list entry

    Args:
        aclname: Name of the access list
        aclaction: Action (allow, deny, refuse, allow_snoop, deny_nonlocal, refuse_nonlocal)
        descr: Optional description
        networks: List of network dicts, each with "network" and "mask" keys (e.g., [{"network": "192.168.1.0", "mask": 24}])
        apply_immediately: Whether to apply changes immediately
    """
    # Validate aclaction
    valid_actions = ("allow", "deny", "refuse", "allow_snoop", "deny_nonlocal", "refuse_nonlocal")
    if aclaction not in valid_actions:
        return {
            "success": False,
            "error": f"Invalid aclaction '{aclaction}'. Must be one of: {', '.join(valid_actions)}",
        }

    client = get_api_client()
    try:
        acl_data = {
            "aclname": aclname,
            "aclaction": aclaction,
        }

        if descr:
            acl_data["descr"] = sanitize_description(descr)

        if networks:
            acl_data["networks"] = networks

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(_ACCESS_LIST, acl_data, control)

        return {
            "success": True,
            "message": f"DNS access list created: {aclname} ({aclaction})",
            "access_list": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create DNS access list: {e}")
        return {"success": False, "error": str(e)}


# --- Apply tool ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_dns_resolver_changes() -> Dict:
    """Apply pending DNS Resolver configuration changes

    Sends a POST to the DNS Resolver apply endpoint to activate any
    pending host override, domain override, access list, or settings changes.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply(_APPLY)

        return {
            "success": True,
            "message": "DNS Resolver changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply DNS Resolver changes: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_dns_access_list(
    access_list_id: int,
    aclname: Optional[str] = None,
    aclaction: Optional[str] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing DNS Resolver access list

    Args:
        access_list_id: Access list ID
        aclname: Access list name
        aclaction: Action (allow, deny, refuse, allow_snoop, deny_non_local, refuse_non_local)
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates = {}
        if aclname is not None:
            updates["aclname"] = aclname
        if aclaction is not None:
            updates["aclaction"] = aclaction
        if descr is not None:
            updates["descr"] = sanitize_description(descr)

        if not updates:
            return {"success": False, "error": "No fields to update — provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(
            "/services/dns_resolver/access_list", access_list_id, updates, control
        )

        return {
            "success": True,
            "message": f"DNS access list {access_list_id} updated",
            "access_list_id": access_list_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update DNS access list: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_dns_access_list(
    access_list_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a DNS Resolver access list. WARNING: This is irreversible.

    Args:
        access_list_id: Access list ID
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(
            "/services/dns_resolver/access_list", access_list_id, control
        )

        return {
            "success": True,
            "message": f"DNS access list {access_list_id} deleted",
            "access_list_id": access_list_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query access lists before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete DNS access list: {e}")
        return {"success": False, "error": str(e)}
