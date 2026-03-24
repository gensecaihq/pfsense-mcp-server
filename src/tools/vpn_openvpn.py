"""OpenVPN management tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from ..helpers import (
    create_default_sort,
    create_pagination,
    sanitize_description,
    validate_port_value,
    validate_subnet,
)
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# 1. search_openvpn_servers
# ---------------------------------------------------------------------------

from ..guardrails import guarded
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_openvpn_servers(
    search_term: Optional[str] = None,
    protocol: Optional[str] = None,
    interface: Optional[str] = None,
    mode: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "descr",
) -> Dict:
    """Search OpenVPN server instances with filtering and pagination.

    Args:
        search_term: Search in server descriptions
        protocol: Filter by protocol (UDP4, TCP4, UDP6, TCP6, etc.)
        interface: Filter by interface (wan, lan, etc.)
        mode: Filter by server mode (p2p_tls, server_tls, server_user, server_tls_user, p2p_shared_key)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (description, protocol, dev_mode, etc.)
    """
    client = get_api_client()
    try:
        filters: List[QueryFilter] = []

        if search_term:
            filters.append(QueryFilter("descr", search_term, "contains"))
        if protocol:
            filters.append(QueryFilter("protocol", protocol))
        if interface:
            filters.append(QueryFilter("interface", interface))
        if mode:
            filters.append(QueryFilter("mode", mode))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/openvpn/servers",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "protocol": protocol,
                "interface": interface,
                "mode": mode,
            },
            "count": len(result.get("data") or []),
            "openvpn_servers": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search OpenVPN servers: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 2. create_openvpn_server
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_openvpn_server(
    mode: str,
    protocol: str,
    dev_mode: str,
    interface: str,
    local_port: int,
    description: Optional[str] = None,
    tls: Optional[str] = None,
    ca: Optional[str] = None,
    cert: Optional[str] = None,
    dh_length: Optional[int] = None,
    tunnel_network: Optional[str] = None,
    local_network: Optional[str] = None,
    remote_network: Optional[str] = None,
    crypto: Optional[str] = None,
    digest: Optional[str] = None,
    dns_server1: Optional[str] = None,
    dns_server2: Optional[str] = None,
    compression: Optional[str] = None,
    duplicate_cn: Optional[bool] = None,
    dynamic_ip: Optional[bool] = None,
    topology: Optional[str] = None,
    maxclients: Optional[int] = None,
    custom_options: Optional[str] = None,
    disabled: bool = False,
    apply_immediately: bool = True,
) -> Dict:
    """Create an OpenVPN server instance on pfSense.

    Args:
        mode: Server mode (p2p_tls, server_tls, server_user, server_tls_user, p2p_shared_key)
        protocol: Protocol (UDP4, TCP4, UDP6, TCP6)
        dev_mode: Device mode (tun or tap)
        interface: Interface to bind to (wan, lan, any, etc.)
        local_port: Local port number for the server to listen on
        description: Optional description for the server instance
        tls: TLS key for additional authentication (base64 or reference)
        ca: Certificate Authority reference/name
        cert: Server certificate reference/name
        dh_length: Diffie-Hellman parameter length (1024, 2048, 3072, 4096)
        tunnel_network: Tunnel network CIDR (e.g., 10.0.8.0/24)
        local_network: Local network(s) accessible to clients (e.g., 192.168.1.0/24)
        remote_network: Remote network(s) accessible from server
        crypto: Data encryption algorithm (e.g., AES-256-GCM)
        digest: Auth digest algorithm (e.g., SHA256)
        dns_server1: DNS server 1 pushed to clients
        dns_server2: DNS server 2 pushed to clients
        compression: Compression setting (omit, no, adaptive, lz4, lz4-v2, lzo, stub, stub-v2)
        duplicate_cn: Allow duplicate client certificates
        dynamic_ip: Allow dynamic IP addressing for clients
        topology: Topology type (subnet or net30)
        maxclients: Maximum number of concurrent clients
        custom_options: Custom OpenVPN options (advanced)
        disabled: Whether the server starts disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        # Validate port
        port_error = validate_port_value(str(local_port), "local_port")
        if port_error:
            return {"success": False, "error": port_error}

        # Validate tunnel_network if provided
        if tunnel_network:
            subnet_error = validate_subnet(tunnel_network)
            if subnet_error:
                return {"success": False, "error": subnet_error}

        # Validate dev_mode
        if dev_mode not in ("tun", "tap"):
            return {"success": False, "error": f"Invalid dev_mode '{dev_mode}'. Must be 'tun' or 'tap'."}

        # Validate dh_length
        if dh_length is not None and dh_length not in (1024, 2048, 3072, 4096):
            return {"success": False, "error": f"Invalid dh_length {dh_length}. Must be 1024, 2048, 3072, or 4096."}

        server_data: Dict = {
            "mode": mode,
            "protocol": protocol,
            "dev_mode": dev_mode,
            "interface": interface,
            "local_port": local_port,
            "disabled": disabled,
        }

        if description:
            server_data["descr"] = sanitize_description(description)
        else:
            server_data["descr"] = f"OpenVPN server via MCP at {datetime.now(timezone.utc).isoformat()}"

        optional_fields = {
            "tls": tls,
            "ca": ca,
            "cert": cert,
            "dh_length": dh_length,
            "tunnel_network": tunnel_network,
            "local_network": local_network,
            "remote_network": remote_network,
            "crypto": crypto,
            "digest": digest,
            "dns_server1": dns_server1,
            "dns_server2": dns_server2,
            "compression": compression,
            "duplicate_cn": duplicate_cn,
            "dynamic_ip": dynamic_ip,
            "topology": topology,
            "maxclients": maxclients,
            "custom_options": custom_options,
        }

        for field_name, value in optional_fields.items():
            if value is not None:
                server_data[field_name] = value

        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_create("/vpn/openvpn/server", server_data, control)

        return {
            "success": True,
            "message": f"OpenVPN server created: {protocol} on port {local_port} ({mode})",
            "openvpn_server": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create OpenVPN server: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 3. update_openvpn_server
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_openvpn_server(
    server_id: int,
    mode: Optional[str] = None,
    protocol: Optional[str] = None,
    dev_mode: Optional[str] = None,
    interface: Optional[str] = None,
    local_port: Optional[int] = None,
    description: Optional[str] = None,
    tls: Optional[str] = None,
    ca: Optional[str] = None,
    cert: Optional[str] = None,
    dh_length: Optional[int] = None,
    tunnel_network: Optional[str] = None,
    local_network: Optional[str] = None,
    remote_network: Optional[str] = None,
    crypto: Optional[str] = None,
    digest: Optional[str] = None,
    dns_server1: Optional[str] = None,
    dns_server2: Optional[str] = None,
    compression: Optional[str] = None,
    duplicate_cn: Optional[bool] = None,
    dynamic_ip: Optional[bool] = None,
    topology: Optional[str] = None,
    maxclients: Optional[int] = None,
    custom_options: Optional[str] = None,
    disabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing OpenVPN server instance by ID.

    Args:
        server_id: Server ID (from search_openvpn_servers)
        mode: Server mode (p2p_tls, server_tls, server_user, server_tls_user, p2p_shared_key)
        protocol: Protocol (UDP4, TCP4, UDP6, TCP6)
        dev_mode: Device mode (tun or tap)
        interface: Interface to bind to (wan, lan, any, etc.)
        local_port: Local port number
        description: Server description
        tls: TLS key for additional authentication
        ca: Certificate Authority reference/name
        cert: Server certificate reference/name
        dh_length: Diffie-Hellman parameter length (1024, 2048, 3072, 4096)
        tunnel_network: Tunnel network CIDR (e.g., 10.0.8.0/24)
        local_network: Local network(s) accessible to clients
        remote_network: Remote network(s) accessible from server
        crypto: Data encryption algorithm
        digest: Auth digest algorithm
        dns_server1: DNS server 1 pushed to clients
        dns_server2: DNS server 2 pushed to clients
        compression: Compression setting
        duplicate_cn: Allow duplicate client certificates
        dynamic_ip: Allow dynamic IP addressing for clients
        topology: Topology type (subnet or net30)
        maxclients: Maximum number of concurrent clients
        custom_options: Custom OpenVPN options (advanced)
        disabled: Whether the server is disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        # Validate optional fields if provided
        if local_port is not None:
            port_error = validate_port_value(str(local_port), "local_port")
            if port_error:
                return {"success": False, "error": port_error}

        if tunnel_network is not None:
            subnet_error = validate_subnet(tunnel_network)
            if subnet_error:
                return {"success": False, "error": subnet_error}

        if dev_mode is not None and dev_mode not in ("tun", "tap"):
            return {"success": False, "error": f"Invalid dev_mode '{dev_mode}'. Must be 'tun' or 'tap'."}

        if dh_length is not None and dh_length not in (1024, 2048, 3072, 4096):
            return {"success": False, "error": f"Invalid dh_length {dh_length}. Must be 1024, 2048, 3072, or 4096."}

        params = {
            "mode": mode,
            "protocol": protocol,
            "dev_mode": dev_mode,
            "interface": interface,
            "local_port": local_port,
            "descr": description,
            "tls": tls,
            "ca": ca,
            "cert": cert,
            "dh_length": dh_length,
            "tunnel_network": tunnel_network,
            "local_network": local_network,
            "remote_network": remote_network,
            "crypto": crypto,
            "digest": digest,
            "dns_server1": dns_server1,
            "dns_server2": dns_server2,
            "compression": compression,
            "duplicate_cn": duplicate_cn,
            "dynamic_ip": dynamic_ip,
            "topology": topology,
            "maxclients": maxclients,
            "custom_options": custom_options,
            "disabled": disabled,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_update("/vpn/openvpn/server", server_id, updates, control)

        return {
            "success": True,
            "message": f"OpenVPN server {server_id} updated",
            "server_id": server_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update OpenVPN server: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 4. delete_openvpn_server
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_openvpn_server(
    server_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an OpenVPN server instance by ID. WARNING: This is irreversible.

    Args:
        server_id: Server ID (from search_openvpn_servers)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_delete("/vpn/openvpn/server", server_id, control)

        return {
            "success": True,
            "message": f"OpenVPN server {server_id} deleted",
            "server_id": server_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query servers before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete OpenVPN server: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 5. search_openvpn_clients
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_openvpn_clients(
    search_term: Optional[str] = None,
    protocol: Optional[str] = None,
    interface: Optional[str] = None,
    server_addr: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "descr",
) -> Dict:
    """Search OpenVPN client instances with filtering and pagination.

    Args:
        search_term: Search in client descriptions
        protocol: Filter by protocol (UDP4, TCP4, UDP6, TCP6, etc.)
        interface: Filter by interface (wan, lan, etc.)
        server_addr: Filter by server address/hostname
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (description, protocol, server_addr, etc.)
    """
    client = get_api_client()
    try:
        filters: List[QueryFilter] = []

        if search_term:
            filters.append(QueryFilter("descr", search_term, "contains"))
        if protocol:
            filters.append(QueryFilter("protocol", protocol))
        if interface:
            filters.append(QueryFilter("interface", interface))
        if server_addr:
            filters.append(QueryFilter("server_addr", server_addr, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/openvpn/clients",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "protocol": protocol,
                "interface": interface,
                "server_addr": server_addr,
            },
            "count": len(result.get("data") or []),
            "openvpn_clients": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search OpenVPN clients: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 6. create_openvpn_client
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_openvpn_client(
    server_addr: str,
    server_port: int,
    protocol: str,
    dev_mode: str,
    interface: str,
    description: Optional[str] = None,
    tls: Optional[str] = None,
    ca: Optional[str] = None,
    cert: Optional[str] = None,
    tunnel_network: Optional[str] = None,
    remote_network: Optional[str] = None,
    crypto: Optional[str] = None,
    digest: Optional[str] = None,
    compression: Optional[str] = None,
    auth_user: Optional[str] = None,
    auth_pass: Optional[str] = None,
    proxy_addr: Optional[str] = None,
    proxy_port: Optional[int] = None,
    proxy_authtype: Optional[str] = None,
    custom_options: Optional[str] = None,
    disabled: bool = False,
    apply_immediately: bool = True,
) -> Dict:
    """Create an OpenVPN client instance on pfSense.

    Args:
        server_addr: Remote server address (IP or hostname)
        server_port: Remote server port number
        protocol: Protocol (UDP4, TCP4, UDP6, TCP6)
        dev_mode: Device mode (tun or tap)
        interface: Interface to bind to (wan, lan, any, etc.)
        description: Optional description for the client instance
        tls: TLS key for additional authentication
        ca: Certificate Authority reference/name
        cert: Client certificate reference/name
        tunnel_network: Tunnel network CIDR (e.g., 10.0.8.0/24)
        remote_network: Remote network(s) accessible via tunnel
        crypto: Data encryption algorithm (e.g., AES-256-GCM)
        digest: Auth digest algorithm (e.g., SHA256)
        compression: Compression setting (omit, no, adaptive, lz4, lz4-v2, lzo, stub, stub-v2)
        auth_user: Username for user authentication
        auth_pass: Password for user authentication
        proxy_addr: HTTP proxy address
        proxy_port: HTTP proxy port
        proxy_authtype: Proxy authentication type (none, basic, ntlm)
        custom_options: Custom OpenVPN options (advanced)
        disabled: Whether the client starts disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        # Validate port
        port_error = validate_port_value(str(server_port), "server_port")
        if port_error:
            return {"success": False, "error": port_error}

        if dev_mode not in ("tun", "tap"):
            return {"success": False, "error": f"Invalid dev_mode '{dev_mode}'. Must be 'tun' or 'tap'."}

        if tunnel_network:
            subnet_error = validate_subnet(tunnel_network)
            if subnet_error:
                return {"success": False, "error": subnet_error}

        client_data: Dict = {
            "server_addr": server_addr,
            "server_port": server_port,
            "protocol": protocol,
            "dev_mode": dev_mode,
            "interface": interface,
            "disabled": disabled,
        }

        if description:
            client_data["descr"] = sanitize_description(description)
        else:
            client_data["descr"] = f"OpenVPN client via MCP at {datetime.now(timezone.utc).isoformat()}"

        optional_fields = {
            "tls": tls,
            "ca": ca,
            "cert": cert,
            "tunnel_network": tunnel_network,
            "remote_network": remote_network,
            "crypto": crypto,
            "digest": digest,
            "compression": compression,
            "auth_user": auth_user,
            "auth_pass": auth_pass,
            "proxy_addr": proxy_addr,
            "proxy_port": proxy_port,
            "proxy_authtype": proxy_authtype,
            "custom_options": custom_options,
        }

        for field_name, value in optional_fields.items():
            if value is not None:
                client_data[field_name] = value

        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_create("/vpn/openvpn/client", client_data, control)

        return {
            "success": True,
            "message": f"OpenVPN client created: {server_addr}:{server_port} ({protocol})",
            "openvpn_client": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create OpenVPN client: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 7. update_openvpn_client
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_openvpn_client(
    client_id: int,
    server_addr: Optional[str] = None,
    server_port: Optional[int] = None,
    protocol: Optional[str] = None,
    dev_mode: Optional[str] = None,
    interface: Optional[str] = None,
    description: Optional[str] = None,
    tls: Optional[str] = None,
    ca: Optional[str] = None,
    cert: Optional[str] = None,
    tunnel_network: Optional[str] = None,
    remote_network: Optional[str] = None,
    crypto: Optional[str] = None,
    digest: Optional[str] = None,
    compression: Optional[str] = None,
    auth_user: Optional[str] = None,
    auth_pass: Optional[str] = None,
    proxy_addr: Optional[str] = None,
    proxy_port: Optional[int] = None,
    proxy_authtype: Optional[str] = None,
    custom_options: Optional[str] = None,
    disabled: Optional[bool] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing OpenVPN client instance by ID.

    Args:
        client_id: Client ID (from search_openvpn_clients)
        server_addr: Remote server address (IP or hostname)
        server_port: Remote server port number
        protocol: Protocol (UDP4, TCP4, UDP6, TCP6)
        dev_mode: Device mode (tun or tap)
        interface: Interface to bind to
        description: Client description
        tls: TLS key for additional authentication
        ca: Certificate Authority reference/name
        cert: Client certificate reference/name
        tunnel_network: Tunnel network CIDR
        remote_network: Remote network(s) accessible via tunnel
        crypto: Data encryption algorithm
        digest: Auth digest algorithm
        compression: Compression setting
        auth_user: Username for user authentication
        auth_pass: Password for user authentication
        proxy_addr: HTTP proxy address
        proxy_port: HTTP proxy port
        proxy_authtype: Proxy authentication type
        custom_options: Custom OpenVPN options (advanced)
        disabled: Whether the client is disabled
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        if server_port is not None:
            port_error = validate_port_value(str(server_port), "server_port")
            if port_error:
                return {"success": False, "error": port_error}

        if dev_mode is not None and dev_mode not in ("tun", "tap"):
            return {"success": False, "error": f"Invalid dev_mode '{dev_mode}'. Must be 'tun' or 'tap'."}

        if tunnel_network is not None:
            subnet_error = validate_subnet(tunnel_network)
            if subnet_error:
                return {"success": False, "error": subnet_error}

        params = {
            "server_addr": server_addr,
            "server_port": server_port,
            "protocol": protocol,
            "dev_mode": dev_mode,
            "interface": interface,
            "descr": description,
            "tls": tls,
            "ca": ca,
            "cert": cert,
            "tunnel_network": tunnel_network,
            "remote_network": remote_network,
            "crypto": crypto,
            "digest": digest,
            "compression": compression,
            "auth_user": auth_user,
            "auth_pass": auth_pass,
            "proxy_addr": proxy_addr,
            "proxy_port": proxy_port,
            "proxy_authtype": proxy_authtype,
            "custom_options": custom_options,
            "disabled": disabled,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_update("/vpn/openvpn/client", client_id, updates, control)

        return {
            "success": True,
            "message": f"OpenVPN client {client_id} updated",
            "client_id": client_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update OpenVPN client: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 8. delete_openvpn_client
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_openvpn_client(
    client_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an OpenVPN client instance by ID. WARNING: This is irreversible.

    Args:
        client_id: Client ID (from search_openvpn_clients)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)

        result = await client.crud_delete("/vpn/openvpn/client", client_id, control)

        return {
            "success": True,
            "message": f"OpenVPN client {client_id} deleted",
            "client_id": client_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query clients before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete OpenVPN client: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 9. search_openvpn_csos
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_openvpn_csos(
    search_term: Optional[str] = None,
    common_name: Optional[str] = None,
    server_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "descr",
) -> Dict:
    """Search OpenVPN Client Specific Overrides (CSOs) with filtering and pagination.

    CSOs allow per-client configuration overrides such as static IPs, custom routes,
    and pushed settings.

    Args:
        search_term: Search in CSO descriptions
        common_name: Filter by client common name (CN)
        server_id: Filter by associated OpenVPN server ID
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (description, common_name, etc.)
    """
    client = get_api_client()
    try:
        filters: List[QueryFilter] = []

        if search_term:
            filters.append(QueryFilter("descr", search_term, "contains"))
        if common_name:
            filters.append(QueryFilter("common_name", common_name))
        if server_id is not None:
            filters.append(QueryFilter("server_id", str(server_id)))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/vpn/openvpn/csos",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "common_name": common_name,
                "server_id": server_id,
            },
            "count": len(result.get("data") or []),
            "openvpn_csos": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search OpenVPN CSOs: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 10. manage_openvpn_cso
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
async def manage_openvpn_cso(
    action: str,
    cso_id: Optional[int] = None,
    common_name: Optional[str] = None,
    server_id: Optional[int] = None,
    description: Optional[str] = None,
    tunnel_network: Optional[str] = None,
    local_network: Optional[str] = None,
    remote_network: Optional[str] = None,
    redirect_gateway: Optional[bool] = None,
    dns_server1: Optional[str] = None,
    dns_server2: Optional[str] = None,
    push_reset: Optional[bool] = None,
    block: Optional[bool] = None,
    custom_options: Optional[str] = None,
    disabled: Optional[bool] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Create, update, or delete an OpenVPN Client Specific Override (CSO).

    CSOs allow per-client configuration such as assigning static tunnel IPs,
    pushing custom routes, or blocking specific clients.

    Args:
        action: Action to perform: "create", "update", or "delete"
        cso_id: CSO ID (required for update and delete)
        common_name: Client common name (CN) - required for create
        server_id: Associated OpenVPN server ID
        description: CSO description
        tunnel_network: Client tunnel network/IP (e.g., 10.0.8.5/32 for static IP)
        local_network: Local network(s) pushed to this client
        remote_network: Remote network(s) for this client
        redirect_gateway: Whether to redirect all client traffic through the tunnel
        dns_server1: DNS server 1 pushed to this client
        dns_server2: DNS server 2 pushed to this client
        push_reset: Reset all pushed options before applying CSO
        block: Block this client from connecting
        custom_options: Custom OpenVPN options for this client
        disabled: Whether the CSO is disabled
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    action_lower = action.lower().strip()

    if action_lower not in ("create", "update", "delete"):
        return {"success": False, "error": f"Invalid action '{action}'. Must be 'create', 'update', or 'delete'."}

    try:
        control = ControlParameters(apply=apply_immediately)

        # --- DELETE ---
        if action_lower == "delete":
            if cso_id is None:
                return {"success": False, "error": "cso_id is required for delete action."}
            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete OpenVPN CSO {cso_id}.",
                }

            result = await client.crud_delete("/vpn/openvpn/cso", cso_id, control)

            return {
                "success": True,
                "message": f"OpenVPN CSO {cso_id} deleted",
                "cso_id": cso_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query CSOs before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # --- BUILD DATA for create/update ---
        cso_data: Dict = {}

        field_map = {
            "common_name": common_name,
            "server_id": server_id,
            "descr": description,
            "tunnel_network": tunnel_network,
            "local_network": local_network,
            "remote_network": remote_network,
            "redirect_gateway": redirect_gateway,
            "dns_server1": dns_server1,
            "dns_server2": dns_server2,
            "push_reset": push_reset,
            "block": block,
            "custom_options": custom_options,
            "disabled": disabled,
        }

        for field_name, value in field_map.items():
            if value is not None:
                if field_name == "descr":
                    cso_data[field_name] = sanitize_description(str(value))
                else:
                    cso_data[field_name] = value

        if tunnel_network:
            subnet_error = validate_subnet(tunnel_network)
            if subnet_error:
                return {"success": False, "error": subnet_error}

        # --- CREATE ---
        if action_lower == "create":
            if not common_name:
                return {"success": False, "error": "common_name is required for create action."}

            if "descr" not in cso_data:
                cso_data["descr"] = f"CSO for {common_name} via MCP at {datetime.now(timezone.utc).isoformat()}"

            result = await client.crud_create("/vpn/openvpn/cso", cso_data, control)

            return {
                "success": True,
                "message": f"OpenVPN CSO created for common name '{common_name}'",
                "openvpn_cso": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # --- UPDATE ---
        if cso_id is None:
            return {"success": False, "error": "cso_id is required for update action."}

        if not cso_data:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        result = await client.crud_update("/vpn/openvpn/cso", cso_id, cso_data, control)

        return {
            "success": True,
            "message": f"OpenVPN CSO {cso_id} updated",
            "cso_id": cso_id,
            "fields_updated": list(cso_data.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to {action_lower} OpenVPN CSO: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 11. get_openvpn_status
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_openvpn_status() -> Dict:
    """Get the runtime status of all OpenVPN server and client instances.

    Returns connection status, connected clients, traffic statistics,
    and uptime information for all active OpenVPN tunnels.
    """
    client = get_api_client()
    try:
        server_status = await client.crud_list("/status/openvpn/servers")
        client_status = await client.crud_list("/status/openvpn/clients")

        return {
            "success": True,
            "servers": {
                "count": len(server_status.get("data") or []),
                "instances": server_status.get("data") or [],
            },
            "clients": {
                "count": len(client_status.get("data") or []),
                "instances": client_status.get("data") or [],
            },
            "links": {
                **client.extract_links(server_status),
                **client.extract_links(client_status),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get OpenVPN status: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 12. export_openvpn_client_config
# ---------------------------------------------------------------------------

@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def export_openvpn_client_config(
    server_id: int,
    common_name: Optional[str] = None,
    export_type: Optional[str] = None,
    hostname: Optional[str] = None,
    port: Optional[int] = None,
    random_local_port: Optional[bool] = None,
    use_tls: Optional[bool] = None,
    use_token: Optional[bool] = None,
    proxy_mode: Optional[str] = None,
    proxy_addr: Optional[str] = None,
    proxy_port: Optional[int] = None,
    proxy_authtype: Optional[str] = None,
    silent_install: Optional[bool] = None,
) -> Dict:
    """Export an OpenVPN client configuration file or installer package.

    Generates downloadable client configuration for connecting to a
    pfSense OpenVPN server instance.

    Args:
        server_id: OpenVPN server ID to export configuration for
        common_name: Client common name (CN) for which to generate config
        export_type: Export format (config, viscosity, inline, etc.)
        hostname: Override hostname/IP in the exported config
        port: Override port in the exported config
        random_local_port: Use a random local port in client config
        use_tls: Include TLS key in the exported config
        use_token: Include token authentication
        proxy_mode: Proxy mode for client config
        proxy_addr: Proxy address for client config
        proxy_port: Proxy port for client config
        proxy_authtype: Proxy authentication type
        silent_install: Silent install mode for Windows installers
    """
    client = get_api_client()
    try:
        export_data: Dict = {
            "server_id": server_id,
        }

        optional_fields = {
            "common_name": common_name,
            "export_type": export_type,
            "hostname": hostname,
            "port": port,
            "random_local_port": random_local_port,
            "use_tls": use_tls,
            "use_token": use_token,
            "proxy_mode": proxy_mode,
            "proxy_addr": proxy_addr,
            "proxy_port": proxy_port,
            "proxy_authtype": proxy_authtype,
            "silent_install": silent_install,
        }

        for field_name, value in optional_fields.items():
            if value is not None:
                export_data[field_name] = value

        result = await client.crud_create("/vpn/openvpn/client_export", export_data)

        return {
            "success": True,
            "message": f"OpenVPN client config exported for server {server_id}",
            "server_id": server_id,
            "common_name": common_name,
            "export": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to export OpenVPN client config: {e}")
        return {"success": False, "error": str(e)}
