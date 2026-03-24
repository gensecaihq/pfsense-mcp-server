"""ACME / Let's Encrypt package tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..helpers import create_pagination, create_default_sort, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------


from ..guardrails import guarded
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_acme_certificates(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search ACME (Let's Encrypt) certificates with filtering and pagination

    Requires the ACME package to be installed on pfSense.

    Args:
        search_term: Search in certificate name/description (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, descr, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/acme/certificates",
            sort=sort,
            pagination=pagination,
        )

        certificates = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            certificates = [
                c for c in certificates
                if term_lower in c.get("name", "").lower()
                or term_lower in c.get("descr", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(certificates),
            "certificates": certificates,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search ACME certificates: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_acme_certificate(
    name: str,
    descr: Optional[str] = None,
    acmeaccount: Optional[str] = None,
    keylength: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an ACME certificate entry

    Args:
        name: Certificate name
        descr: Optional description
        acmeaccount: ACME account key reference name (from search_acme_account_keys)
        keylength: Key length/type (e.g., '2048', '4096', 'ec-256', 'ec-384')
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        cert_data: Dict = {"name": name}

        if descr:
            cert_data["descr"] = sanitize_description(descr)
        if acmeaccount:
            cert_data["acmeaccount"] = acmeaccount
        if keylength:
            cert_data["keylength"] = keylength

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/services/acme/certificate", cert_data, control)

        return {
            "success": True,
            "message": f"ACME certificate '{name}' created",
            "certificate": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create ACME certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_acme_certificate(
    certificate_id: int,
    name: Optional[str] = None,
    descr: Optional[str] = None,
    acmeaccount: Optional[str] = None,
    keylength: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing ACME certificate entry by ID

    Args:
        certificate_id: Certificate ID (from search_acme_certificates)
        name: Certificate name
        descr: Description
        acmeaccount: ACME account key reference name
        keylength: Key length/type
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "name": name,
            "descr": descr,
            "acmeaccount": acmeaccount,
            "keylength": keylength,
        }

        updates: Dict = {}
        for param_name, value in params.items():
            if value is not None:
                if param_name == "descr":
                    updates[param_name] = sanitize_description(value)
                else:
                    updates[param_name] = value

        if not updates:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_update("/services/acme/certificate", certificate_id, updates, control)

        return {
            "success": True,
            "message": f"ACME certificate {certificate_id} updated",
            "certificate_id": certificate_id,
            "fields_updated": list(updates.keys()),
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update ACME certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_acme_certificate(
    certificate_id: int,
    apply_immediately: bool = True,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete an ACME certificate entry by ID. WARNING: This is irreversible.

    Args:
        certificate_id: Certificate ID (from search_acme_certificates)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_delete("/services/acme/certificate", certificate_id, control)

        return {
            "success": True,
            "message": f"ACME certificate {certificate_id} deleted",
            "certificate_id": certificate_id,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query certificates before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete ACME certificate: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Certificate Issue & Renew
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def issue_acme_certificate(
    id: int,
) -> Dict:
    """Issue (obtain) an ACME certificate from Let's Encrypt

    Triggers the ACME challenge/validation process and obtains the certificate.

    Args:
        id: Certificate ID to issue (from search_acme_certificates)
    """
    client = get_api_client()
    try:
        issue_data: Dict = {"id": id}
        control = ControlParameters(apply=True)
        result = await client.crud_create("/services/acme/certificate/issue", issue_data, control)

        return {
            "success": True,
            "message": f"ACME certificate {id} issue requested",
            "certificate_id": id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to issue ACME certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def renew_acme_certificate(
    id: int,
) -> Dict:
    """Renew an existing ACME certificate

    Triggers the renewal process for a previously issued certificate.

    Args:
        id: Certificate ID to renew (from search_acme_certificates)
    """
    client = get_api_client()
    try:
        renew_data: Dict = {"id": id}
        control = ControlParameters(apply=True)
        result = await client.crud_create("/services/acme/certificate/renew", renew_data, control)

        return {
            "success": True,
            "message": f"ACME certificate {id} renewal requested",
            "certificate_id": id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to renew ACME certificate: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Account Keys
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_acme_account_keys(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name",
) -> Dict:
    """Search ACME account keys with filtering and pagination

    Args:
        search_term: Search in account key name/description/email (client-side filter)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, descr, email, etc.)
    """
    client = get_api_client()
    try:
        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)

        result = await client.crud_list(
            "/services/acme/account_keys",
            sort=sort,
            pagination=pagination,
        )

        account_keys = result.get("data") or []

        if search_term:
            term_lower = search_term.lower()
            account_keys = [
                k for k in account_keys
                if term_lower in k.get("name", "").lower()
                or term_lower in k.get("descr", "").lower()
                or term_lower in k.get("email", "").lower()
            ]

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(account_keys),
            "account_keys": account_keys,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search ACME account keys: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_acme_account_key(
    name: str,
    email: str,
    descr: Optional[str] = None,
    acmeserver: Optional[str] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an ACME account key for Let's Encrypt

    Args:
        name: Account key name
        email: Contact email address for the ACME account
        descr: Optional description
        acmeserver: ACME server URL (defaults to Let's Encrypt production if omitted)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        key_data: Dict = {
            "name": name,
            "email": email,
        }

        if descr:
            key_data["descr"] = sanitize_description(descr)
        if acmeserver:
            key_data["acmeserver"] = acmeserver

        control = ControlParameters(apply=apply_immediately)
        result = await client.crud_create("/services/acme/account_key", key_data, control)

        return {
            "success": True,
            "message": f"ACME account key '{name}' created for {email}",
            "account_key": result.get("data", result),
            "applied": apply_immediately,
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create ACME account key: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def register_acme_account_key(
    id: int,
) -> Dict:
    """Register an ACME account key with the ACME server (Let's Encrypt)

    This sends the account key to the ACME server and completes registration.

    Args:
        id: Account key ID to register (from search_acme_account_keys)
    """
    client = get_api_client()
    try:
        register_data: Dict = {"id": id}
        control = ControlParameters(apply=True)
        result = await client.crud_create("/services/acme/account_key/register", register_data, control)

        return {
            "success": True,
            "message": f"ACME account key {id} registration requested",
            "account_key_id": id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to register ACME account key: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def get_acme_settings() -> Dict:
    """Get the current ACME package settings"""
    client = get_api_client()
    try:
        result = await client.crud_get_settings("/services/acme/settings")

        return {
            "success": True,
            "settings": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get ACME settings: {e}")
        return {"success": False, "error": str(e)}
