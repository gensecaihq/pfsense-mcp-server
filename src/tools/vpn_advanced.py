"""VPN advanced features tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# IPsec Phase 2 Encryptions
# ---------------------------------------------------------------------------


from ..guardrails import guarded, rate_limited
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_ipsec_phase2_encryptions(
    parent_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "encryption_algorithm_name",
) -> Dict:
    """Search IPsec Phase 2 encryption entries with filtering and pagination

    Args:
        parent_id: Filter by parent Phase 2 ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (encryption_algorithm_name, hash_algorithm, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        if parent_id is not None:
            filters.append(QueryFilter("parent_id", parent_id))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/ipsec/phase2/encryptions",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        encryptions = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"parent_id": parent_id},
            "count": len(encryptions),
            "encryptions": encryptions,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search IPsec Phase 2 encryptions: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def create_ipsec_phase2_encryption(
    parent_id: int,
    encryption_algorithm_name: str,
    encryption_algorithm_keylen: Optional[int] = None,
    hash_algorithm: Optional[str] = None,
    dhgroup: Optional[int] = None,
    prf_algorithm: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an IPsec Phase 2 encryption entry

    Args:
        parent_id: Parent Phase 2 ID
        encryption_algorithm_name: Encryption algorithm name (e.g., 'aes', 'aes128gcm', 'aes256gcm', 'chacha20poly1305')
        encryption_algorithm_keylen: Key length for the encryption algorithm (e.g., 128, 192, 256)
        hash_algorithm: Hash algorithm (e.g., 'hmac_sha256', 'hmac_sha384', 'hmac_sha512', 'aesxcbc')
        dhgroup: DH group number (e.g., 14, 15, 16, 19, 20, 21)
        prf_algorithm: PRF algorithm (e.g., 'prfsha256', 'prfsha384', 'prfsha512')
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        enc_data: Dict = {
            "parent_id": parent_id,
            "encryption_algorithm_name": encryption_algorithm_name,
        }

        if encryption_algorithm_keylen is not None:
            enc_data["encryption_algorithm_keylen"] = encryption_algorithm_keylen
        if hash_algorithm is not None:
            enc_data["hash_algorithm"] = hash_algorithm
        if dhgroup is not None:
            enc_data["dhgroup"] = dhgroup
        if prf_algorithm is not None:
            enc_data["prf_algorithm"] = prf_algorithm

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create(
            "/vpn/ipsec/phase2/encryption", enc_data, control
        )

        return {
            "success": True,
            "message": f"IPsec Phase 2 encryption '{encryption_algorithm_name}' created for Phase 2 {parent_id}",
            "encryption": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create IPsec Phase 2 encryption: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
async def update_ipsec_phase2_encryption(
    encryption_id: int,
    encryption_algorithm_name: Optional[str] = None,
    encryption_algorithm_keylen: Optional[int] = None,
    hash_algorithm: Optional[str] = None,
    dhgroup: Optional[int] = None,
    prf_algorithm: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing IPsec Phase 2 encryption entry by ID

    Args:
        encryption_id: Encryption entry ID (from search_ipsec_phase2_encryptions)
        encryption_algorithm_name: Encryption algorithm name
        encryption_algorithm_keylen: Key length for the encryption algorithm
        hash_algorithm: Hash algorithm
        dhgroup: DH group number
        prf_algorithm: PRF algorithm
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        updates: Dict = {}

        if encryption_algorithm_name is not None:
            updates["encryption_algorithm_name"] = encryption_algorithm_name
        if encryption_algorithm_keylen is not None:
            updates["encryption_algorithm_keylen"] = encryption_algorithm_keylen
        if hash_algorithm is not None:
            updates["hash_algorithm"] = hash_algorithm
        if dhgroup is not None:
            updates["dhgroup"] = dhgroup
        if prf_algorithm is not None:
            updates["prf_algorithm"] = prf_algorithm

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update(
            "/vpn/ipsec/phase2/encryption", encryption_id, updates, control
        )

        return {
            "success": True,
            "message": f"IPsec Phase 2 encryption {encryption_id} updated",
            "encryption_id": encryption_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update IPsec Phase 2 encryption: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_ipsec_phase2_encryption(
    encryption_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an IPsec Phase 2 encryption entry by ID. WARNING: This is irreversible.

    Args:
        encryption_id: Encryption entry ID (from search_ipsec_phase2_encryptions)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete(
            "/vpn/ipsec/phase2/encryption", encryption_id, control
        )

        return {
            "success": True,
            "message": f"IPsec Phase 2 encryption {encryption_id} deleted",
            "encryption_id": encryption_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query encryptions before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete IPsec Phase 2 encryption: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# WireGuard Tunnel Addresses
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_wireguard_tunnel_addresses(
    parent_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "address",
) -> Dict:
    """Search WireGuard tunnel addresses with filtering and pagination

    Args:
        parent_id: Filter by parent tunnel ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (address, descr, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        if parent_id is not None:
            filters.append(QueryFilter("parent_id", parent_id))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/wireguard/tunnel/addresses",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        addresses = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"parent_id": parent_id},
            "count": len(addresses),
            "tunnel_addresses": addresses,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search WireGuard tunnel addresses: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def manage_wireguard_tunnel_address(
    action: str,
    tunnel_id: int,
    address: Optional[str] = None,
    descr: Optional[str] = None,
    address_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Add or remove an address for a WireGuard tunnel

    Args:
        action: Action to perform ('create' or 'delete')
        tunnel_id: Parent tunnel ID
        address: IP address/subnet to assign (required for create, e.g., '10.0.0.1/24')
        descr: Optional description (used for create)
        address_id: Address ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not address:
                return {"success": False, "error": "address is required for create action"}

            addr_data: Dict = {
                "parent_id": tunnel_id,
                "address": address,
            }
            if descr is not None:
                addr_data["descr"] = sanitize_description(descr)

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create(
                "/vpn/wireguard/tunnel/address", addr_data, control
            )

            return {
                "success": True,
                "message": f"Address '{address}' added to WireGuard tunnel {tunnel_id}",
                "tunnel_address": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if address_id is None:
                return {"success": False, "error": "address_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete address {address_id} from tunnel {tunnel_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete(
                "/vpn/wireguard/tunnel/address",
                address_id,
                control,
                extra_data={"parent_id": tunnel_id},
            )

            return {
                "success": True,
                "message": f"Address {address_id} removed from WireGuard tunnel {tunnel_id}",
                "address_id": address_id,
                "tunnel_id": tunnel_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query tunnel addresses before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }

    except Exception as e:
        logger.error(f"Failed to manage WireGuard tunnel address: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# OpenVPN Status
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_openvpn_server_status() -> Dict:
    """Get the status of all OpenVPN servers"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/status/openvpn/servers")

        return {
            "success": True,
            "servers": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get OpenVPN server status: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_openvpn_client_status() -> Dict:
    """Get the status of all OpenVPN clients"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/status/openvpn/clients")

        return {
            "success": True,
            "clients": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get OpenVPN client status: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_openvpn_server_connections(
    server_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "common_name",
) -> Dict:
    """Search active OpenVPN server connections

    Args:
        server_id: Filter by OpenVPN server ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (common_name, real_address, virtual_address, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        if server_id is not None:
            filters.append(QueryFilter("server_id", server_id))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/status/openvpn/server/connections",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        connections = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"server_id": server_id},
            "count": len(connections),
            "connections": connections,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search OpenVPN server connections: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def disconnect_openvpn_client(
    connection_id: int,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Disconnect an active OpenVPN client connection. WARNING: This will terminate the client session.

    Args:
        connection_id: Connection ID (from search_openvpn_server_connections)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        result = await client.crud_delete(
            "/status/openvpn/server/connection", connection_id
        )

        return {
            "success": True,
            "message": f"OpenVPN client connection {connection_id} disconnected",
            "connection_id": connection_id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query connections before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to disconnect OpenVPN client: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_openvpn_server_routes(
    server_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "common_name",
) -> Dict:
    """Search OpenVPN server routing table entries

    Args:
        server_id: Filter by OpenVPN server ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (common_name, virtual_address, real_address, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        if server_id is not None:
            filters.append(QueryFilter("server_id", server_id))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/status/openvpn/server/routes",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        routes = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"server_id": server_id},
            "count": len(routes),
            "routes": routes,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search OpenVPN server routes: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# OpenVPN Client Export Configs
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_openvpn_client_export_configs(
    server_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "common_name",
) -> Dict:
    """Search available OpenVPN client export configurations

    Args:
        server_id: Filter by OpenVPN server ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (common_name, server_id, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        if server_id is not None:
            filters.append(QueryFilter("server_id", server_id))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/openvpn/client_export/configs",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        configs = result.get("data") or []

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"server_id": server_id},
            "count": len(configs),
            "export_configs": configs,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search OpenVPN client export configs: {e}")
        return {"success": False, "error": str(e)}
