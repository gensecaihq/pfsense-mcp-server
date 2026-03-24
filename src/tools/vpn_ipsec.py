"""IPsec VPN tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, Optional

from ..helpers import (
    create_default_sort,
    create_pagination,
    sanitize_description,
    validate_ip_address,
)
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Phase 1 (IKE SA) tools
# ---------------------------------------------------------------------------


from ..guardrails import guarded
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_ipsec_phase1s(
    remote_gateway: Optional[str] = None,
    iketype: Optional[str] = None,
    search_description: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "descr",
) -> Dict:
    """Search IPsec Phase 1 (IKE) entries with filtering and pagination

    Args:
        remote_gateway: Filter by remote gateway IP address
        iketype: Filter by IKE type (ikev1, ikev2, auto)
        search_description: Search in entry descriptions
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (descr, remote_gateway, iketype, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if remote_gateway:
            filters.append(QueryFilter("remote_gateway", remote_gateway))

        if iketype:
            filters.append(QueryFilter("iketype", iketype))

        if search_description:
            filters.append(QueryFilter("descr", search_description, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/ipsec/phase1s",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "remote_gateway": remote_gateway,
                "iketype": iketype,
                "search_description": search_description,
            },
            "count": len(result.get("data") or []),
            "phase1s": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search IPsec Phase 1 entries: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_ipsec_phase1(
    iketype: str,
    protocol: str,
    interface: str,
    remote_gateway: str,
    authentication_method: str,
    pre_shared_key: Optional[str] = None,
    myid_type: Optional[str] = None,
    myid_data: Optional[str] = None,
    peerid_type: Optional[str] = None,
    peerid_data: Optional[str] = None,
    lifetime: Optional[int] = None,
    descr: Optional[str] = None,
    disabled: bool = False,
    apply_immediately: bool = True,
) -> Dict:
    """Create an IPsec Phase 1 (IKE) entry

    Args:
        iketype: IKE version (ikev1, ikev2, auto)
        protocol: Protocol (inet for IPv4, inet6 for IPv6, both)
        interface: Interface for the tunnel (wan, lan, etc.)
        remote_gateway: Remote gateway IP address or hostname
        authentication_method: Auth method (pre_shared_key, cert)
        pre_shared_key: Pre-shared key (required when authentication_method is pre_shared_key)
        myid_type: Local identifier type (myaddress, address, fqdn, user_fqdn, asn1dn, keyid)
        myid_data: Local identifier data
        peerid_type: Peer identifier type (peeraddress, address, fqdn, user_fqdn, asn1dn, keyid)
        peerid_data: Peer identifier data
        lifetime: SA lifetime in seconds (default is typically 28800)
        descr: Description for this Phase 1 entry
        disabled: Whether this entry starts disabled
        apply_immediately: Whether to apply changes immediately
    """
    # Validate remote gateway IP if it looks like an IP address
    if remote_gateway and remote_gateway[0].isdigit():
        try:
            validate_ip_address(remote_gateway)
        except ValueError as e:
            return {"success": False, "error": f"Invalid remote_gateway: {e}"}

    allowed_iketypes = ("ikev1", "ikev2", "auto")
    if iketype not in allowed_iketypes:
        return {"success": False, "error": f"iketype must be one of: {', '.join(allowed_iketypes)}"}

    client = get_api_client()
    try:
        phase1_data = {
            "iketype": iketype,
            "protocol": protocol,
            "interface": interface,
            "remote_gateway": remote_gateway,
            "authentication_method": authentication_method,
            "disabled": disabled,
        }

        if pre_shared_key is not None:
            phase1_data["pre_shared_key"] = pre_shared_key
        if myid_type is not None:
            phase1_data["myid_type"] = myid_type
        if myid_data is not None:
            phase1_data["myid_data"] = myid_data
        if peerid_type is not None:
            phase1_data["peerid_type"] = peerid_type
        if peerid_data is not None:
            phase1_data["peerid_data"] = peerid_data
        if lifetime is not None:
            phase1_data["lifetime"] = lifetime

        if descr:
            phase1_data["descr"] = sanitize_description(descr)
        else:
            phase1_data["descr"] = f"IPsec P1 via MCP at {datetime.now(timezone.utc).isoformat()}"

        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_create("/vpn/ipsec/phase1", phase1_data, control)

        return {
            "success": True,
            "message": f"IPsec Phase 1 created: {interface} -> {remote_gateway} ({iketype})",
            "phase1": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create IPsec Phase 1: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_ipsec_phase1(
    phase1_id: int,
    iketype: Optional[str] = None,
    protocol: Optional[str] = None,
    interface: Optional[str] = None,
    remote_gateway: Optional[str] = None,
    authentication_method: Optional[str] = None,
    pre_shared_key: Optional[str] = None,
    myid_type: Optional[str] = None,
    myid_data: Optional[str] = None,
    peerid_type: Optional[str] = None,
    peerid_data: Optional[str] = None,
    lifetime: Optional[int] = None,
    descr: Optional[str] = None,
    disabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing IPsec Phase 1 (IKE) entry by ID

    Args:
        phase1_id: Phase 1 entry ID (from search_ipsec_phase1s)
        iketype: IKE version (ikev1, ikev2, auto)
        protocol: Protocol (inet, inet6, both)
        interface: Interface for the tunnel (wan, lan, etc.)
        remote_gateway: Remote gateway IP address or hostname
        authentication_method: Auth method (pre_shared_key, cert)
        pre_shared_key: Pre-shared key
        myid_type: Local identifier type
        myid_data: Local identifier data
        peerid_type: Peer identifier type
        peerid_data: Peer identifier data
        lifetime: SA lifetime in seconds
        descr: Description
        disabled: Whether entry is disabled
        apply_immediately: Whether to apply changes immediately
    """
    if iketype is not None and iketype not in ("ikev1", "ikev2", "auto"):
        return {"success": False, "error": "iketype must be one of: ikev1, ikev2, auto"}

    client = get_api_client()
    try:
        field_map = {
            "iketype": "iketype",
            "protocol": "protocol",
            "interface": "interface",
            "remote_gateway": "remote_gateway",
            "authentication_method": "authentication_method",
            "pre_shared_key": "pre_shared_key",
            "myid_type": "myid_type",
            "myid_data": "myid_data",
            "peerid_type": "peerid_type",
            "peerid_data": "peerid_data",
            "lifetime": "lifetime",
            "descr": "descr",
            "disabled": "disabled",
        }

        params = {
            "iketype": iketype,
            "protocol": protocol,
            "interface": interface,
            "remote_gateway": remote_gateway,
            "authentication_method": authentication_method,
            "pre_shared_key": pre_shared_key,
            "myid_type": myid_type,
            "myid_data": myid_data,
            "peerid_type": peerid_type,
            "peerid_data": peerid_data,
            "lifetime": lifetime,
            "descr": descr,
            "disabled": disabled,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_update("/vpn/ipsec/phase1", phase1_id, updates, control)

        return {
            "success": True,
            "message": f"IPsec Phase 1 {phase1_id} updated",
            "phase1_id": phase1_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update IPsec Phase 1: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_ipsec_phase1(
    phase1_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an IPsec Phase 1 (IKE) entry by ID. WARNING: This is irreversible and will also remove associated Phase 2 entries.

    Args:
        phase1_id: Phase 1 entry ID (from search_ipsec_phase1s)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/vpn/ipsec/phase1", phase1_id, control)

        return {
            "success": True,
            "message": f"IPsec Phase 1 {phase1_id} deleted",
            "phase1_id": phase1_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query Phase 1 entries before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete IPsec Phase 1: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Phase 2 (Child SA) tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_ipsec_phase2s(
    ikeid: Optional[int] = None,
    mode: Optional[str] = None,
    search_description: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "descr",
) -> Dict:
    """Search IPsec Phase 2 (Child SA / tunnel) entries with filtering and pagination

    Args:
        ikeid: Filter by parent Phase 1 IKE ID
        mode: Filter by mode (tunnel, transport, vti)
        search_description: Search in entry descriptions
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (descr, mode, ikeid, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if ikeid is not None:
            filters.append(QueryFilter("ikeid", str(ikeid)))

        if mode:
            filters.append(QueryFilter("mode", mode))

        if search_description:
            filters.append(QueryFilter("descr", search_description, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/ipsec/phase2s",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "ikeid": ikeid,
                "mode": mode,
                "search_description": search_description,
            },
            "count": len(result.get("data") or []),
            "phase2s": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search IPsec Phase 2 entries: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_ipsec_phase2(
    ikeid: int,
    mode: str,
    localid_type: str,
    localid_address: Optional[str] = None,
    localid_netbits: Optional[int] = None,
    remoteid_type: Optional[str] = None,
    remoteid_address: Optional[str] = None,
    remoteid_netbits: Optional[int] = None,
    protocol: Optional[str] = None,
    lifetime: Optional[int] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an IPsec Phase 2 (Child SA / tunnel) entry

    Args:
        ikeid: Parent Phase 1 IKE ID to associate this Phase 2 with
        mode: Tunnel mode (tunnel, transport, vti)
        localid_type: Local network type (address, network, lan, none)
        localid_address: Local network address (required when localid_type is address or network)
        localid_netbits: Local network prefix length (e.g., 24 for /24; required when localid_type is network)
        remoteid_type: Remote network type (address, network, none)
        remoteid_address: Remote network address (required when remoteid_type is address or network)
        remoteid_netbits: Remote network prefix length (e.g., 24; required when remoteid_type is network)
        protocol: IPsec protocol (esp, ah)
        lifetime: SA lifetime in seconds (default is typically 3600)
        descr: Description for this Phase 2 entry
        apply_immediately: Whether to apply changes immediately
    """
    allowed_modes = ("tunnel", "transport", "vti")
    if mode not in allowed_modes:
        return {"success": False, "error": f"mode must be one of: {', '.join(allowed_modes)}"}

    client = get_api_client()
    try:
        phase2_data = {
            "ikeid": ikeid,
            "mode": mode,
            "localid_type": localid_type,
        }

        if localid_address is not None:
            phase2_data["localid_address"] = localid_address
        if localid_netbits is not None:
            phase2_data["localid_netbits"] = localid_netbits
        if remoteid_type is not None:
            phase2_data["remoteid_type"] = remoteid_type
        if remoteid_address is not None:
            phase2_data["remoteid_address"] = remoteid_address
        if remoteid_netbits is not None:
            phase2_data["remoteid_netbits"] = remoteid_netbits
        if protocol is not None:
            phase2_data["protocol"] = protocol
        if lifetime is not None:
            phase2_data["lifetime"] = lifetime

        if descr:
            phase2_data["descr"] = sanitize_description(descr)
        else:
            phase2_data["descr"] = f"IPsec P2 via MCP at {datetime.now(timezone.utc).isoformat()}"

        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_create("/vpn/ipsec/phase2", phase2_data, control)

        return {
            "success": True,
            "message": f"IPsec Phase 2 created for IKE ID {ikeid} ({mode})",
            "phase2": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create IPsec Phase 2: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_ipsec_phase2(
    phase2_id: int,
    ikeid: Optional[int] = None,
    mode: Optional[str] = None,
    localid_type: Optional[str] = None,
    localid_address: Optional[str] = None,
    localid_netbits: Optional[int] = None,
    remoteid_type: Optional[str] = None,
    remoteid_address: Optional[str] = None,
    remoteid_netbits: Optional[int] = None,
    protocol: Optional[str] = None,
    lifetime: Optional[int] = None,
    descr: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing IPsec Phase 2 (Child SA / tunnel) entry by ID

    Args:
        phase2_id: Phase 2 entry ID (from search_ipsec_phase2s)
        ikeid: Parent Phase 1 IKE ID
        mode: Tunnel mode (tunnel, transport, vti)
        localid_type: Local network type (address, network, lan, none)
        localid_address: Local network address
        localid_netbits: Local network prefix length
        remoteid_type: Remote network type (address, network, none)
        remoteid_address: Remote network address
        remoteid_netbits: Remote network prefix length
        protocol: IPsec protocol (esp, ah)
        lifetime: SA lifetime in seconds
        descr: Description
        apply_immediately: Whether to apply changes immediately
    """
    if mode is not None and mode not in ("tunnel", "transport", "vti"):
        return {"success": False, "error": "mode must be one of: tunnel, transport, vti"}

    client = get_api_client()
    try:
        field_map = {
            "ikeid": "ikeid",
            "mode": "mode",
            "localid_type": "localid_type",
            "localid_address": "localid_address",
            "localid_netbits": "localid_netbits",
            "remoteid_type": "remoteid_type",
            "remoteid_address": "remoteid_address",
            "remoteid_netbits": "remoteid_netbits",
            "protocol": "protocol",
            "lifetime": "lifetime",
            "descr": "descr",
        }

        params = {
            "ikeid": ikeid,
            "mode": mode,
            "localid_type": localid_type,
            "localid_address": localid_address,
            "localid_netbits": localid_netbits,
            "remoteid_type": remoteid_type,
            "remoteid_address": remoteid_address,
            "remoteid_netbits": remoteid_netbits,
            "protocol": protocol,
            "lifetime": lifetime,
            "descr": descr,
        }

        updates = {}
        for param_name, value in params.items():
            if value is not None:
                updates[field_map[param_name]] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_update("/vpn/ipsec/phase2", phase2_id, updates, control)

        return {
            "success": True,
            "message": f"IPsec Phase 2 {phase2_id} updated",
            "phase2_id": phase2_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update IPsec Phase 2: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_ipsec_phase2(
    phase2_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an IPsec Phase 2 (Child SA / tunnel) entry by ID. WARNING: This is irreversible.

    Args:
        phase2_id: Phase 2 entry ID (from search_ipsec_phase2s)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/vpn/ipsec/phase2", phase2_id, control)

        return {
            "success": True,
            "message": f"IPsec Phase 2 {phase2_id} deleted",
            "phase2_id": phase2_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query Phase 2 entries before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete IPsec Phase 2: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Phase 1 Encryption tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_ipsec_phase1_encryptions(
    parent_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "encryption_algorithm_name",
) -> Dict:
    """Search IPsec Phase 1 encryption algorithm entries with filtering and pagination

    Args:
        parent_id: Filter by parent Phase 1 ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (encryption_algorithm_name, hash_algorithm, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if parent_id is not None:
            filters.append(QueryFilter("parent_id", str(parent_id)))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/ipsec/phase1/encryptions",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "parent_id": parent_id,
            },
            "count": len(result.get("data") or []),
            "encryptions": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search IPsec Phase 1 encryptions: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_ipsec_phase1_encryption(
    parent_id: int,
    encryption_algorithm_name: str,
    encryption_algorithm_keylen: Optional[int] = None,
    hash_algorithm: Optional[str] = None,
    dhgroup: Optional[int] = None,
    prf_algorithm: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an IPsec Phase 1 encryption algorithm entry

    Args:
        parent_id: Parent Phase 1 ID to associate this encryption with
        encryption_algorithm_name: Encryption algorithm (aes, aes128gcm, aes192gcm, aes256gcm, blowfish, 3des, cast128)
        encryption_algorithm_keylen: Key length in bits (128, 192, 256; required for variable-length algorithms like AES)
        hash_algorithm: Hash algorithm (sha1, sha256, sha384, sha512, aesxcbc, md5)
        dhgroup: Diffie-Hellman group number (1, 2, 5, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 28, 29, 30, 31, 32)
        prf_algorithm: PRF algorithm for IKEv2 (sha1, sha256, sha384, sha512, aesxcbc)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        enc_data = {
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

        result = await client.crud_create("/vpn/ipsec/phase1/encryption", enc_data, control)

        return {
            "success": True,
            "message": f"IPsec Phase 1 encryption created: {encryption_algorithm_name} for Phase 1 {parent_id}",
            "encryption": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create IPsec Phase 1 encryption: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_ipsec_phase1_encryption(
    encryption_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an IPsec Phase 1 encryption algorithm entry by ID. WARNING: This is irreversible.

    Args:
        encryption_id: Encryption entry ID (from search_ipsec_phase1_encryptions)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/vpn/ipsec/phase1/encryption", encryption_id, control)

        return {
            "success": True,
            "message": f"IPsec Phase 1 encryption {encryption_id} deleted",
            "encryption_id": encryption_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query encryptions before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete IPsec Phase 1 encryption: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Apply & Status tools
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def apply_ipsec_changes() -> Dict:
    """Apply pending IPsec configuration changes to the live system.

    Call this after making IPsec configuration changes with apply_immediately=False
    to activate them all at once.
    """
    client = get_api_client()
    try:
        result = await client.crud_apply("/vpn/ipsec/apply")

        return {
            "success": True,
            "message": "IPsec changes applied successfully",
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to apply IPsec changes: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_ipsec_status() -> Dict:
    """Get IPsec Security Associations (SAs) status showing active tunnels and their state.

    Returns the current state of all IPsec IKE SAs including connection status,
    established time, local/remote identities, and child SA counts.
    """
    client = get_api_client()
    try:
        result = await client.crud_list("/status/ipsec/sas")

        return {
            "success": True,
            "count": len(result.get("data") or []),
            "sas": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get IPsec SA status: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_ipsec_child_sa_status() -> Dict:
    """Get IPsec Child Security Associations status showing active tunnel details.

    Returns detailed status of all IPsec Child SAs including traffic selectors,
    bytes transferred, encryption/integrity algorithms in use, and uptime.
    """
    client = get_api_client()
    try:
        result = await client.crud_list("/status/ipsec/child_sas")

        return {
            "success": True,
            "count": len(result.get("data") or []),
            "child_sas": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get IPsec Child SA status: {e}")
        return {"success": False, "error": str(e)}
