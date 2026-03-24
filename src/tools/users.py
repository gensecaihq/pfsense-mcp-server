"""User and group management tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_default_sort, create_pagination, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ------------------------------------------------------------------ #
# Users
# ------------------------------------------------------------------ #


from ..guardrails import guarded
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_users(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search pfSense local users with optional filtering and pagination

    Args:
        search_term: Search term to filter users by name or description
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, descr, disabled, expires, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if search_term:
            filters.append(QueryFilter("name", search_term, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.get_users(
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
            },
            "count": len(result.get("data") or []),
            "users": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search users: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_user(
    name: str,
    password: str,
    priv: Optional[List[str]] = None,
    descr: Optional[str] = None,
    disabled: bool = False,
    expires: Optional[str] = None,
    authorizedkeys: Optional[str] = None,
    ipsecpsk: Optional[str] = None,
) -> Dict:
    """Create a new pfSense local user

    Args:
        name: Username (login name)
        password: User password
        priv: List of privileges to assign (e.g., ["page-all", "user-shell-access"])
        descr: User description / full name
        disabled: Whether the user account starts disabled
        expires: Account expiration date (MM/DD/YYYY format)
        authorizedkeys: SSH authorized public keys (base64 encoded)
        ipsecpsk: IPsec Pre-Shared Key for this user
    """
    client = get_api_client()
    try:
        if not name or not name.strip():
            return {"success": False, "error": "name is required and cannot be empty"}
        if not password or not password.strip():
            return {"success": False, "error": "password is required and cannot be empty"}

        user_data: Dict = {
            "name": name.strip(),
            "password": password,
            "disabled": disabled,
        }

        if priv is not None:
            user_data["priv"] = priv

        if descr:
            user_data["descr"] = sanitize_description(descr)

        if expires:
            user_data["expires"] = expires

        if authorizedkeys:
            user_data["authorizedkeys"] = authorizedkeys

        if ipsecpsk:
            user_data["ipsecpsk"] = ipsecpsk

        result = await client.create_user(user_data)

        return {
            "success": True,
            "message": f"User '{name}' created successfully",
            "user": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_user(
    user_id: int,
    name: Optional[str] = None,
    password: Optional[str] = None,
    priv: Optional[List[str]] = None,
    descr: Optional[str] = None,
    disabled: Optional[bool] = None,
    expires: Optional[str] = None,
    authorizedkeys: Optional[str] = None,
    ipsecpsk: Optional[str] = None,
) -> Dict:
    """Update an existing pfSense local user by ID

    Args:
        user_id: User ID (array index from search_users)
        name: Username (login name)
        password: New password
        priv: List of privileges to assign (replaces existing)
        descr: User description / full name
        disabled: Whether the user account is disabled
        expires: Account expiration date (MM/DD/YYYY format)
        authorizedkeys: SSH authorized public keys (base64 encoded)
        ipsecpsk: IPsec Pre-Shared Key
    """
    client = get_api_client()
    try:
        field_map = {
            "name": "name",
            "password": "password",
            "priv": "priv",
            "descr": "descr",
            "disabled": "disabled",
            "expires": "expires",
            "authorizedkeys": "authorizedkeys",
            "ipsecpsk": "ipsecpsk",
        }

        params = {
            "name": name,
            "password": password,
            "priv": priv,
            "descr": descr,
            "disabled": disabled,
            "expires": expires,
            "authorizedkeys": authorizedkeys,
            "ipsecpsk": ipsecpsk,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                api_field = field_map[param_name]
                if param_name == "descr" and isinstance(value, str):
                    updates[api_field] = sanitize_description(value)
                else:
                    updates[api_field] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        updates["id"] = user_id

        result = await client.update_user(updates)

        return {
            "success": True,
            "message": f"User {user_id} updated",
            "user_id": user_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update user: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_user(
    user_id: int,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a pfSense local user by ID. WARNING: This is irreversible.

    Args:
        user_id: User ID (array index from search_users)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        result = await client.delete_user(user_id)

        return {
            "success": True,
            "message": f"User {user_id} deleted",
            "user_id": user_id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query users before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        return {"success": False, "error": str(e)}


# ------------------------------------------------------------------ #
# Groups
# ------------------------------------------------------------------ #


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_groups(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search pfSense user groups with optional filtering and pagination

    Args:
        search_term: Search term to filter groups by name or description
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, descr, scope, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if search_term:
            filters.append(QueryFilter("name", search_term, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.get_groups(
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
            },
            "count": len(result.get("data") or []),
            "groups": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search groups: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_group(
    name: str,
    scope: str = "local",
    descr: Optional[str] = None,
    priv: Optional[List[str]] = None,
    member: Optional[List[int]] = None,
) -> Dict:
    """Create a new pfSense user group

    Args:
        name: Group name
        scope: Group scope (local or remote)
        descr: Group description
        priv: List of privileges to assign to the group
        member: List of user IDs to add as members
    """
    client = get_api_client()
    try:
        if not name or not name.strip():
            return {"success": False, "error": "name is required and cannot be empty"}

        if scope not in ("local", "remote"):
            return {"success": False, "error": "scope must be 'local' or 'remote'"}

        group_data: Dict = {
            "name": name.strip(),
            "scope": scope,
        }

        if descr:
            group_data["descr"] = sanitize_description(descr)

        if priv is not None:
            group_data["priv"] = priv

        if member is not None:
            group_data["member"] = member

        result = await client.create_group(group_data)

        return {
            "success": True,
            "message": f"Group '{name}' created successfully",
            "group": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create group: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_group(
    group_id: int,
    name: Optional[str] = None,
    scope: Optional[str] = None,
    descr: Optional[str] = None,
    priv: Optional[List[str]] = None,
    member: Optional[List[int]] = None,
) -> Dict:
    """Update an existing pfSense user group by ID

    Args:
        group_id: Group ID (array index from search_groups)
        name: Group name
        scope: Group scope (local or remote)
        descr: Group description
        priv: List of privileges (replaces existing)
        member: List of user IDs (replaces existing membership)
    """
    client = get_api_client()
    try:
        if scope is not None and scope not in ("local", "remote"):
            return {"success": False, "error": "scope must be 'local' or 'remote'"}

        field_map = {
            "name": "name",
            "scope": "scope",
            "descr": "descr",
            "priv": "priv",
            "member": "member",
        }

        params = {
            "name": name,
            "scope": scope,
            "descr": descr,
            "priv": priv,
            "member": member,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                api_field = field_map[param_name]
                if param_name == "descr" and isinstance(value, str):
                    updates[api_field] = sanitize_description(value)
                else:
                    updates[api_field] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        updates["id"] = group_id

        result = await client.update_group(updates)

        return {
            "success": True,
            "message": f"Group {group_id} updated",
            "group_id": group_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update group: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_group(
    group_id: int,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a pfSense user group by ID. WARNING: This is irreversible.

    Args:
        group_id: Group ID (array index from search_groups)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        result = await client.delete_group(group_id)

        return {
            "success": True,
            "message": f"Group {group_id} deleted",
            "group_id": group_id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query groups before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete group: {e}")
        return {"success": False, "error": str(e)}


# ------------------------------------------------------------------ #
# Auth Servers
# ------------------------------------------------------------------ #


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_auth_servers(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search pfSense authentication servers (LDAP, RADIUS) with optional filtering

    Args:
        search_term: Search term to filter auth servers by name
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, type, host, etc.)
    """
    client = get_api_client()
    try:
        filters = []

        if search_term:
            filters.append(QueryFilter("name", search_term, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.get_auth_servers(
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
            },
            "count": len(result.get("data") or []),
            "auth_servers": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search auth servers: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_auth_server(
    name: str,
    type: str,
    host: str,
    port: Optional[int] = None,
    transport: Optional[str] = None,
    scope: Optional[str] = None,
    basedn: Optional[str] = None,
    authcn: Optional[str] = None,
    ldap_attr_user: Optional[str] = None,
    ldap_attr_group: Optional[str] = None,
    ldap_attr_member: Optional[str] = None,
    ldap_binddn: Optional[str] = None,
    ldap_bindpw: Optional[str] = None,
    radius_secret: Optional[str] = None,
    radius_auth_port: Optional[int] = None,
    radius_acct_port: Optional[int] = None,
    radius_protocol: Optional[str] = None,
    radius_timeout: Optional[int] = None,
) -> Dict:
    """Create a new authentication server (LDAP or RADIUS)

    Args:
        name: Descriptive name for this auth server
        type: Server type - "ldap" or "radius"
        host: Hostname or IP address of the auth server
        port: Port number (default: 389 for LDAP, 636 for LDAPS, 1812 for RADIUS)
        transport: Transport protocol for LDAP ("tcp", "ssl", "starttls")
        scope: LDAP search scope ("one" for one level, "subtree" for entire subtree)
        basedn: LDAP base DN for searches (e.g., "dc=example,dc=com")
        authcn: LDAP authentication container(s) (e.g., "CN=Users;DC=example,DC=com")
        ldap_attr_user: LDAP username attribute (e.g., "uid" or "samAccountName")
        ldap_attr_group: LDAP group attribute (e.g., "cn")
        ldap_attr_member: LDAP group member attribute (e.g., "member" or "memberOf")
        ldap_binddn: LDAP bind DN for authenticated binds
        ldap_bindpw: LDAP bind password
        radius_secret: RADIUS shared secret
        radius_auth_port: RADIUS authentication port (default: 1812)
        radius_acct_port: RADIUS accounting port (default: 1813)
        radius_protocol: RADIUS protocol ("MSCHAPv2", "MSCHAPv1", "CHAP_MD5", "PAP")
        radius_timeout: RADIUS timeout in seconds
    """
    client = get_api_client()
    try:
        if not name or not name.strip():
            return {"success": False, "error": "name is required and cannot be empty"}

        if type not in ("ldap", "radius"):
            return {"success": False, "error": "type must be 'ldap' or 'radius'"}

        if not host or not host.strip():
            return {"success": False, "error": "host is required and cannot be empty"}

        server_data: Dict = {
            "name": name.strip(),
            "type": type,
            "host": host.strip(),
        }

        if port is not None:
            server_data["port"] = port

        # LDAP-specific fields
        if transport is not None:
            if transport not in ("tcp", "ssl", "starttls"):
                return {"success": False, "error": "transport must be 'tcp', 'ssl', or 'starttls'"}
            server_data["transport"] = transport

        if scope is not None:
            if scope not in ("one", "subtree"):
                return {"success": False, "error": "scope must be 'one' or 'subtree'"}
            server_data["scope"] = scope

        if basedn is not None:
            server_data["basedn"] = basedn

        if authcn is not None:
            server_data["authcn"] = authcn

        if ldap_attr_user is not None:
            server_data["ldap_attr_user"] = ldap_attr_user

        if ldap_attr_group is not None:
            server_data["ldap_attr_group"] = ldap_attr_group

        if ldap_attr_member is not None:
            server_data["ldap_attr_member"] = ldap_attr_member

        if ldap_binddn is not None:
            server_data["ldap_binddn"] = ldap_binddn

        if ldap_bindpw is not None:
            server_data["ldap_bindpw"] = ldap_bindpw

        # RADIUS-specific fields
        if radius_secret is not None:
            server_data["radius_secret"] = radius_secret

        if radius_auth_port is not None:
            server_data["radius_auth_port"] = radius_auth_port

        if radius_acct_port is not None:
            server_data["radius_acct_port"] = radius_acct_port

        if radius_protocol is not None:
            allowed_protocols = ("MSCHAPv2", "MSCHAPv1", "CHAP_MD5", "PAP")
            if radius_protocol not in allowed_protocols:
                return {"success": False, "error": f"radius_protocol must be one of: {', '.join(allowed_protocols)}"}
            server_data["radius_protocol"] = radius_protocol

        if radius_timeout is not None:
            server_data["radius_timeout"] = radius_timeout

        result = await client.create_auth_server(server_data)

        return {
            "success": True,
            "message": f"Auth server '{name}' ({type}) created successfully",
            "auth_server": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create auth server: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_auth_server(
    auth_server_id: int,
    name: Optional[str] = None,
    type: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    transport: Optional[str] = None,
    scope: Optional[str] = None,
    basedn: Optional[str] = None,
    authcn: Optional[str] = None,
    ldap_attr_user: Optional[str] = None,
    ldap_attr_group: Optional[str] = None,
    ldap_attr_member: Optional[str] = None,
    ldap_binddn: Optional[str] = None,
    ldap_bindpw: Optional[str] = None,
    radius_secret: Optional[str] = None,
    radius_auth_port: Optional[int] = None,
    radius_acct_port: Optional[int] = None,
    radius_protocol: Optional[str] = None,
    radius_timeout: Optional[int] = None,
) -> Dict:
    """Update an existing authentication server by ID

    Args:
        auth_server_id: Auth server ID (array index from search_auth_servers)
        name: Descriptive name for this auth server
        type: Server type - "ldap" or "radius"
        host: Hostname or IP address of the auth server
        port: Port number
        transport: Transport protocol for LDAP ("tcp", "ssl", "starttls")
        scope: LDAP search scope ("one" or "subtree")
        basedn: LDAP base DN for searches
        authcn: LDAP authentication container(s)
        ldap_attr_user: LDAP username attribute
        ldap_attr_group: LDAP group attribute
        ldap_attr_member: LDAP group member attribute
        ldap_binddn: LDAP bind DN
        ldap_bindpw: LDAP bind password
        radius_secret: RADIUS shared secret
        radius_auth_port: RADIUS authentication port
        radius_acct_port: RADIUS accounting port
        radius_protocol: RADIUS protocol ("MSCHAPv2", "MSCHAPv1", "CHAP_MD5", "PAP")
        radius_timeout: RADIUS timeout in seconds
    """
    client = get_api_client()
    try:
        # Validate enum fields if provided
        if type is not None and type not in ("ldap", "radius"):
            return {"success": False, "error": "type must be 'ldap' or 'radius'"}

        if transport is not None and transport not in ("tcp", "ssl", "starttls"):
            return {"success": False, "error": "transport must be 'tcp', 'ssl', or 'starttls'"}

        if scope is not None and scope not in ("one", "subtree"):
            return {"success": False, "error": "scope must be 'one' or 'subtree'"}

        if radius_protocol is not None:
            allowed_protocols = ("MSCHAPv2", "MSCHAPv1", "CHAP_MD5", "PAP")
            if radius_protocol not in allowed_protocols:
                return {"success": False, "error": f"radius_protocol must be one of: {', '.join(allowed_protocols)}"}

        field_map = {
            "name": "name",
            "type": "type",
            "host": "host",
            "port": "port",
            "transport": "transport",
            "scope": "scope",
            "basedn": "basedn",
            "authcn": "authcn",
            "ldap_attr_user": "ldap_attr_user",
            "ldap_attr_group": "ldap_attr_group",
            "ldap_attr_member": "ldap_attr_member",
            "ldap_binddn": "ldap_binddn",
            "ldap_bindpw": "ldap_bindpw",
            "radius_secret": "radius_secret",
            "radius_auth_port": "radius_auth_port",
            "radius_acct_port": "radius_acct_port",
            "radius_protocol": "radius_protocol",
            "radius_timeout": "radius_timeout",
        }

        params = {
            "name": name,
            "type": type,
            "host": host,
            "port": port,
            "transport": transport,
            "scope": scope,
            "basedn": basedn,
            "authcn": authcn,
            "ldap_attr_user": ldap_attr_user,
            "ldap_attr_group": ldap_attr_group,
            "ldap_attr_member": ldap_attr_member,
            "ldap_binddn": ldap_binddn,
            "ldap_bindpw": ldap_bindpw,
            "radius_secret": radius_secret,
            "radius_auth_port": radius_auth_port,
            "radius_acct_port": radius_acct_port,
            "radius_protocol": radius_protocol,
            "radius_timeout": radius_timeout,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                api_field = field_map[param_name]
                updates[api_field] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        updates["id"] = auth_server_id

        result = await client.update_auth_server(updates)

        return {
            "success": True,
            "message": f"Auth server {auth_server_id} updated",
            "auth_server_id": auth_server_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update auth server: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_auth_server(
    auth_server_id: int,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a pfSense authentication server by ID. WARNING: This is irreversible.

    Args:
        auth_server_id: Auth server ID (array index from search_auth_servers)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        result = await client.delete_auth_server(auth_server_id)

        return {
            "success": True,
            "message": f"Auth server {auth_server_id} deleted",
            "auth_server_id": auth_server_id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query auth servers before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete auth server: {e}")
        return {"success": False, "error": str(e)}
