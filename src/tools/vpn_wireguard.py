"""WireGuard VPN tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import create_default_sort, create_pagination
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations

# API endpoint constants
from ..guardrails import guarded, rate_limited
_TUNNELS = "/vpn/wireguard/tunnels"
_TUNNEL = "/vpn/wireguard/tunnel"
_PEERS = "/vpn/wireguard/peers"
_PEER = "/vpn/wireguard/peer"
_PEER_ALLOWED_IPS = "/vpn/wireguard/peer/allowed_ips"
_PEER_ALLOWED_IP = "/vpn/wireguard/peer/allowed_ip"
_SETTINGS = "/vpn/wireguard/settings"
_APPLY = "/vpn/wireguard/apply"


# --- Tunnel tools ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_wireguard_tunnels(
    search_description: Optional[str] = None,
    enabled: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search WireGuard tunnels with filtering and pagination

    Args:
        search_description: Search in tunnel descriptions
        enabled: Filter by enabled status
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, listenport, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if search_description:
            filters.append(QueryFilter("descr", search_description, "contains"))

        if enabled is not None:
            filters.append(QueryFilter("enabled", str(enabled).lower()))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            _TUNNELS,
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_description": search_description,
                "enabled": enabled,
            },
            "count": len(result.get("data") or []),
            "tunnels": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search WireGuard tunnels: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_wireguard_tunnel(
    name: str,
    listenport: int,
    privatekey: str,
    mtu: Optional[int] = None,
    descr: Optional[str] = None,
    enabled: bool = True,
    apply_immediately: bool = True,
) -> Dict:
    """Create a new WireGuard tunnel

    Args:
        name: Tunnel interface name
        listenport: UDP listen port for the tunnel
        privatekey: WireGuard private key for the tunnel
        mtu: Optional MTU for the tunnel interface
        descr: Optional description
        enabled: Whether the tunnel is enabled (default: True)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        tunnel_data = {
            "name": name,
            "listenport": listenport,
            "privatekey": privatekey,
            "enabled": enabled,
        }

        if mtu is not None:
            tunnel_data["mtu"] = mtu
        if descr is not None:
            tunnel_data["descr"] = descr

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(_TUNNEL, tunnel_data, control)

        return {
            "success": True,
            "message": f"WireGuard tunnel '{name}' created on port {listenport}",
            "tunnel": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create WireGuard tunnel: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_wireguard_tunnel(
    tunnel_id: int,
    name: Optional[str] = None,
    listenport: Optional[int] = None,
    privatekey: Optional[str] = None,
    mtu: Optional[int] = None,
    descr: Optional[str] = None,
    enabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing WireGuard tunnel by ID

    Args:
        tunnel_id: Tunnel ID (from search_wireguard_tunnels)
        name: Tunnel interface name
        listenport: UDP listen port
        privatekey: WireGuard private key
        mtu: MTU for the tunnel interface
        descr: Description
        enabled: Whether the tunnel is enabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "name": "name",
            "listenport": "listenport",
            "privatekey": "privatekey",
            "mtu": "mtu",
            "descr": "descr",
            "enabled": "enabled",
        }

        params = {
            "name": name,
            "listenport": listenport,
            "privatekey": privatekey,
            "mtu": mtu,
            "descr": descr,
            "enabled": enabled,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(_TUNNEL, tunnel_id, updates, control)

        return {
            "success": True,
            "message": f"WireGuard tunnel {tunnel_id} updated",
            "tunnel_id": tunnel_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update WireGuard tunnel: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_wireguard_tunnel(
    tunnel_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a WireGuard tunnel by ID. WARNING: This is irreversible.

    Args:
        tunnel_id: Tunnel ID (from search_wireguard_tunnels)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(_TUNNEL, tunnel_id, control)

        return {
            "success": True,
            "message": f"WireGuard tunnel {tunnel_id} deleted",
            "tunnel_id": tunnel_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query tunnels before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete WireGuard tunnel: {e}")
        return {"success": False, "error": str(e)}


# --- Peer tools ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_wireguard_peers(
    search_description: Optional[str] = None,
    tun: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "descr",
) -> Dict:
    """Search WireGuard peers with filtering and pagination

    Args:
        search_description: Search in peer descriptions
        tun: Filter by parent tunnel ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (descr, endpoint, publickey, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if search_description:
            filters.append(QueryFilter("descr", search_description, "contains"))

        if tun is not None:
            filters.append(QueryFilter("tun", str(tun)))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            _PEERS,
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_description": search_description,
                "tun": tun,
            },
            "count": len(result.get("data") or []),
            "peers": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search WireGuard peers: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_wireguard_peer(
    tun: int,
    publickey: str,
    descr: Optional[str] = None,
    endpoint: Optional[str] = None,
    port: Optional[int] = None,
    presharedkey: Optional[str] = None,
    keepalive: Optional[int] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create a new WireGuard peer on a tunnel

    Args:
        tun: Parent tunnel ID the peer belongs to
        publickey: WireGuard public key for the peer
        descr: Optional description
        endpoint: Optional peer endpoint hostname or IP
        port: Optional peer endpoint port
        presharedkey: Optional pre-shared key for additional security
        keepalive: Optional persistent keepalive interval in seconds
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        peer_data = {
            "tun": tun,
            "publickey": publickey,
        }

        if descr is not None:
            peer_data["descr"] = descr
        if endpoint is not None:
            peer_data["endpoint"] = endpoint
        if port is not None:
            peer_data["port"] = port
        if presharedkey is not None:
            peer_data["presharedkey"] = presharedkey
        if keepalive is not None:
            peer_data["keepalive"] = keepalive

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(_PEER, peer_data, control)

        return {
            "success": True,
            "message": f"WireGuard peer created on tunnel {tun}",
            "peer": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create WireGuard peer: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_wireguard_peer(
    peer_id: int,
    tun: Optional[int] = None,
    publickey: Optional[str] = None,
    descr: Optional[str] = None,
    endpoint: Optional[str] = None,
    port: Optional[int] = None,
    presharedkey: Optional[str] = None,
    keepalive: Optional[int] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing WireGuard peer by ID

    Args:
        peer_id: Peer ID (from search_wireguard_peers)
        tun: Parent tunnel ID
        publickey: WireGuard public key
        descr: Description
        endpoint: Peer endpoint hostname or IP
        port: Peer endpoint port
        presharedkey: Pre-shared key
        keepalive: Persistent keepalive interval in seconds
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "tun": "tun",
            "publickey": "publickey",
            "descr": "descr",
            "endpoint": "endpoint",
            "port": "port",
            "presharedkey": "presharedkey",
            "keepalive": "keepalive",
        }

        params = {
            "tun": tun,
            "publickey": publickey,
            "descr": descr,
            "endpoint": endpoint,
            "port": port,
            "presharedkey": presharedkey,
            "keepalive": keepalive,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(_PEER, peer_id, updates, control)

        return {
            "success": True,
            "message": f"WireGuard peer {peer_id} updated",
            "peer_id": peer_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update WireGuard peer: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_wireguard_peer(
    peer_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a WireGuard peer by ID. WARNING: This is irreversible.

    Args:
        peer_id: Peer ID (from search_wireguard_peers)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(_PEER, peer_id, control)

        return {
            "success": True,
            "message": f"WireGuard peer {peer_id} deleted",
            "peer_id": peer_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query peers before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete WireGuard peer: {e}")
        return {"success": False, "error": str(e)}


# --- Peer allowed IP tools ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_wireguard_peer_allowed_ips(
    peer_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "address",
) -> Dict:
    """Search WireGuard peer allowed IPs with filtering and pagination

    Args:
        peer_id: Filter by parent peer ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (address, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if peer_id is not None:
            filters.append(QueryFilter("parent_id", str(peer_id)))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            _PEER_ALLOWED_IPS,
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "peer_id": peer_id,
            },
            "count": len(result.get("data") or []),
            "allowed_ips": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search WireGuard peer allowed IPs: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_wireguard_peer_allowed_ip(
    action: str,
    peer_id: int,
    address: Optional[str] = None,
    descr: Optional[str] = None,
    allowed_ip_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Add or remove an allowed IP for a WireGuard peer

    Args:
        action: Action to perform ('create' or 'delete')
        peer_id: Parent peer ID the allowed IP belongs to
        address: IP address/subnet to allow (required for create, e.g., '10.0.0.0/24')
        descr: Optional description (used for create)
        allowed_ip_id: Allowed IP ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not address:
                return {"success": False, "error": "address is required for create action"}

            ip_data = {
                "parent_id": peer_id,
                "address": address,
            }
            if descr is not None:
                ip_data["descr"] = descr

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create(_PEER_ALLOWED_IP, ip_data, control)

            return {
                "success": True,
                "message": f"Allowed IP '{address}' added to peer {peer_id}",
                "allowed_ip": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if allowed_ip_id is None:
                return {"success": False, "error": "allowed_ip_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete allowed IP {allowed_ip_id} from peer {peer_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete(
                _PEER_ALLOWED_IP, allowed_ip_id, control,
                extra_data={"parent_id": peer_id},
            )

            return {
                "success": True,
                "message": f"Allowed IP {allowed_ip_id} removed from peer {peer_id}",
                "allowed_ip_id": allowed_ip_id,
                "peer_id": peer_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query allowed IPs before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }
    except Exception as e:
        logger.error(f"Failed to manage WireGuard peer allowed IP: {e}")
        return {"success": False, "error": str(e)}


# --- Settings and apply tools ---


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_wireguard_settings() -> Dict:
    """Get the current WireGuard service settings"""
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
        logger.error(f"Failed to get WireGuard settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_wireguard_settings(
    enable: Optional[bool] = None,
    keep_conf: Optional[bool] = None,
    resolve_interval: Optional[int] = None,
    interface_group: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update WireGuard service settings

    Args:
        enable: Enable or disable the WireGuard service
        keep_conf: Whether to keep configuration on package removal
        resolve_interval: DNS resolution interval in seconds
        interface_group: Interface group assignment
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        field_map = {
            "enable": "enable",
            "keep_conf": "keep_conf",
            "resolve_interval": "resolve_interval",
            "interface_group": "interface_group",
        }

        params = {
            "enable": enable,
            "keep_conf": keep_conf,
            "resolve_interval": resolve_interval,
            "interface_group": interface_group,
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
            "message": "WireGuard settings updated",
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update WireGuard settings: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_wireguard_changes() -> Dict:
    """Apply pending WireGuard configuration changes

    Sends a POST to the WireGuard apply endpoint to activate any
    pending tunnel, peer, or settings changes.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply(_APPLY)

        return {
            "success": True,
            "message": "WireGuard changes applied",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply WireGuard changes: {e}")
        return {"success": False, "error": str(e)}
