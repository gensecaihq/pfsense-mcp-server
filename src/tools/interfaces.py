"""Interface tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import create_default_sort, create_pagination, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Interface Configuration
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_interface_configs(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "descr",
) -> Dict:
    """Search interface configurations with filtering and pagination

    Args:
        search_term: General search across interface name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (descr, if, typev4, ipaddr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/interfaces",
            sort=sort,
            pagination=pagination,
        )

        interfaces = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            interfaces = [
                i for i in interfaces
                if term_lower in i.get("descr", "").lower()
                or term_lower in i.get("if", "").lower()
                or term_lower in i.get("ipaddr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(interfaces),
            "interfaces": interfaces,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search interface configs: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_interface(
    interface_port: str,
    enable: bool = True,
    descr: Optional[str] = None,
    typev4: str = "static",
    ipaddr: Optional[str] = None,
    subnet: Optional[int] = None,
    gateway: Optional[str] = None,
    blockpriv: bool = False,
    blockbogons: bool = False,
    apply_immediately: bool = True,
) -> Dict:
    """Create (assign) a network interface

    Args:
        interface_port: Physical port name (e.g., igb0, em0, vtnet0)
        enable: Whether the interface is enabled
        descr: Interface description/friendly name (e.g., LAN2, DMZ)
        typev4: IPv4 configuration type (static, dhcp, none)
        ipaddr: IPv4 address (required if typev4 is static)
        subnet: Subnet mask bits (e.g., 24 for /24, required if typev4 is static)
        gateway: Gateway name for this interface
        blockpriv: Block private networks (RFC 1918)
        blockbogons: Block bogon networks
        apply_immediately: Whether to apply changes immediately
    """
    if typev4 not in ("static", "dhcp", "none"):
        return {"success": False, "error": "typev4 must be 'static', 'dhcp', or 'none'"}

    client = get_api_client()
    try:
        iface_data: Dict[str, Union[str, int, bool]] = {
            "if": interface_port,
            "enable": enable,
            "typev4": typev4,
            "blockpriv": blockpriv,
            "blockbogons": blockbogons,
        }

        if descr:
            iface_data["descr"] = sanitize_description(descr)
        if ipaddr:
            iface_data["ipaddr"] = ipaddr
        if subnet is not None:
            iface_data["subnet"] = subnet
        if gateway:
            iface_data["gateway"] = gateway

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/interface", iface_data, control)

        return {
            "success": True,
            "message": f"Interface created on port {interface_port}" + (f" ({descr})" if descr else ""),
            "interface": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create interface: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_interface(
    interface_id: int,
    enable: Optional[bool] = None,
    descr: Optional[str] = None,
    typev4: Optional[str] = None,
    ipaddr: Optional[str] = None,
    subnet: Optional[int] = None,
    gateway: Optional[str] = None,
    blockpriv: Optional[bool] = None,
    blockbogons: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing interface by ID

    Args:
        interface_id: Interface ID (from search_interface_configs)
        enable: Whether the interface is enabled
        descr: Interface description/friendly name
        typev4: IPv4 configuration type (static, dhcp, none)
        ipaddr: IPv4 address
        subnet: Subnet mask bits
        gateway: Gateway name
        blockpriv: Block private networks (RFC 1918)
        blockbogons: Block bogon networks
        apply_immediately: Whether to apply changes immediately
    """
    if typev4 is not None and typev4 not in ("static", "dhcp", "none"):
        return {"success": False, "error": "typev4 must be 'static', 'dhcp', or 'none'"}

    client = get_api_client()
    try:
        params = {
            "enable": enable,
            "descr": descr,
            "typev4": typev4,
            "ipaddr": ipaddr,
            "subnet": subnet,
            "gateway": gateway,
            "blockpriv": blockpriv,
            "blockbogons": blockbogons,
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
        result = await client.crud_update("/interface", interface_id, updates, control)

        return {
            "success": True,
            "message": f"Interface {interface_id} updated",
            "interface_id": interface_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update interface: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_interface(
    interface_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Delete (unassign) an interface by ID. WARNING: This is irreversible.

    Args:
        interface_id: Interface ID (from search_interface_configs)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will permanently delete interface {interface_id}.",
        }

    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/interface", interface_id, control)

        return {
            "success": True,
            "message": f"Interface {interface_id} deleted",
            "interface_id": interface_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query interfaces before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete interface: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_interface_changes() -> Dict:
    """Apply pending interface changes

    Use this after making changes with apply_immediately=False to batch-apply them.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/interface/apply")

        return {
            "success": True,
            "message": "Interface changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply interface changes: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# VLANs
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_vlans(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "tag",
) -> Dict:
    """Search VLANs with filtering and pagination

    Args:
        search_term: General search across VLAN tag/parent/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (tag, if, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/interface/vlans",
            sort=sort,
            pagination=pagination,
        )

        vlans = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            vlans = [
                v for v in vlans
                if term_lower in str(v.get("tag", "")).lower()
                or term_lower in v.get("if", "").lower()
                or term_lower in v.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(vlans),
            "vlans": vlans,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search VLANs: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_vlan(
    parent_interface: str,
    tag: int,
    pcp: Optional[int] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a VLAN

    Args:
        parent_interface: Parent physical interface (e.g., igb0, em0)
        tag: VLAN tag (1-4094)
        pcp: VLAN priority code point (0-7)
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    if tag < 1 or tag > 4094:
        return {"success": False, "error": "VLAN tag must be between 1 and 4094"}

    if pcp is not None and (pcp < 0 or pcp > 7):
        return {"success": False, "error": "PCP must be between 0 and 7"}

    client = get_api_client()
    try:
        vlan_data: Dict[str, Union[str, int]] = {
            "if": parent_interface,
            "tag": tag,
        }

        if pcp is not None:
            vlan_data["pcp"] = pcp
        if descr:
            vlan_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/interface/vlan", vlan_data, control)

        return {
            "success": True,
            "message": f"VLAN {tag} created on {parent_interface}",
            "vlan": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create VLAN: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_vlan(
    vlan_id: int,
    parent_interface: Optional[str] = None,
    tag: Optional[int] = None,
    pcp: Optional[int] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing VLAN by ID

    Args:
        vlan_id: VLAN ID (from search_vlans)
        parent_interface: Parent physical interface
        tag: VLAN tag (1-4094)
        pcp: VLAN priority code point (0-7)
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    if tag is not None and (tag < 1 or tag > 4094):
        return {"success": False, "error": "VLAN tag must be between 1 and 4094"}

    if pcp is not None and (pcp < 0 or pcp > 7):
        return {"success": False, "error": "PCP must be between 0 and 7"}

    client = get_api_client()
    try:
        updates: Dict[str, Union[str, int]] = {}

        if parent_interface is not None:
            updates["if"] = parent_interface
        if tag is not None:
            updates["tag"] = tag
        if pcp is not None:
            updates["pcp"] = pcp
        if descr is not None:
            updates["descr"] = sanitize_description(descr)

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/interface/vlan", vlan_id, updates, control)

        return {
            "success": True,
            "message": f"VLAN {vlan_id} updated",
            "vlan_id": vlan_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update VLAN: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def delete_vlan(
    vlan_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Delete a VLAN by ID. WARNING: This is irreversible.

    Args:
        vlan_id: VLAN ID (from search_vlans)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
    """
    if not confirm:
        return {
            "success": False,
            "error": "This is a destructive operation. Set confirm=True to proceed.",
            "details": f"Will permanently delete VLAN {vlan_id}.",
        }

    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/interface/vlan", vlan_id, control)

        return {
            "success": True,
            "message": f"VLAN {vlan_id} deleted",
            "vlan_id": vlan_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query VLANs before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete VLAN: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Bridges
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_interface_bridges(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "bridgeif",
) -> Dict:
    """Search interface bridges with filtering and pagination

    Args:
        search_term: General search across bridge members/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (bridgeif, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/interface/bridges",
            sort=sort,
            pagination=pagination,
        )

        bridges = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            bridges = [
                b for b in bridges
                if term_lower in b.get("bridgeif", "").lower()
                or term_lower in b.get("descr", "").lower()
                or term_lower in str(b.get("members", "")).lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(bridges),
            "bridges": bridges,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search interface bridges: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_interface_bridge(
    members: List[str],
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an interface bridge

    Args:
        members: Array of interface names to bridge (e.g., ["lan", "opt1"])
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    if not members or len(members) < 2:
        return {"success": False, "error": "A bridge requires at least 2 member interfaces"}

    client = get_api_client()
    try:
        bridge_data: Dict[str, Union[str, List]] = {
            "members": members,
        }

        if descr:
            bridge_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/interface/bridge", bridge_data, control)

        return {
            "success": True,
            "message": f"Bridge created with members: {', '.join(members)}",
            "bridge": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create interface bridge: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Interface Groups
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_interface_groups(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "ifname",
) -> Dict:
    """Search interface groups with filtering and pagination

    Args:
        search_term: General search across group name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (ifname, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/interface/groups",
            sort=sort,
            pagination=pagination,
        )

        groups = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            groups = [
                g for g in groups
                if term_lower in g.get("ifname", "").lower()
                or term_lower in g.get("descr", "").lower()
                or term_lower in str(g.get("members", "")).lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(groups),
            "interface_groups": groups,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search interface groups: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_interface_group(
    ifname: str,
    members: List[str],
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an interface group

    Args:
        ifname: Group name (alphanumeric, no spaces)
        members: Array of interface names to include (e.g., ["lan", "opt1", "opt2"])
        descr: Optional description
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        group_data: Dict[str, Union[str, List]] = {
            "ifname": ifname,
            "members": members,
        }

        if descr:
            group_data["descr"] = sanitize_description(descr)

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/interface/group", group_data, control)

        return {
            "success": True,
            "message": f"Interface group '{ifname}' created with members: {', '.join(members)}",
            "interface_group": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create interface group: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Available Interfaces
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_available_interfaces() -> Dict:
    """Get a list of available (unassigned) network interfaces"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/interface/available_interfaces")

        return {
            "success": True,
            "available_interfaces": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get available interfaces: {e}")
        return {"success": False, "error": str(e)}
