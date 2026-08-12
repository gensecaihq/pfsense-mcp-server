"""ACME / Let's Encrypt package tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from mcp.types import ToolAnnotations

# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------
from ..guardrails import guarded, rate_limited
from ..helpers import (
    create_default_sort,
    create_pagination,
    create_search_pagination,
    field_contains,
    sanitize_description,
)
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp


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
        pagination, page, page_size = create_search_pagination(page, page_size, search_term)
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
                if field_contains(c, "name", term_lower)
                or field_contains(c, "descr", term_lower)
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
@rate_limited
async def create_acme_certificate(
    name: str,
    a_domainlist: List[Dict],
    descr: Optional[str] = None,
    acmeaccount: Optional[str] = None,
    keylength: Optional[str] = None,
    dnssleep: Optional[int] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Create an ACME certificate entry

    The pfSense API rejects a certificate with no domains ("Field
    `a_domainlist` is required"), so at least one domain/SAN validation entry
    must be provided at creation time.

    Args:
        name: Certificate name
        a_domainlist: List of domain (SAN) validation entries. Each dict needs:
            - name: fully-qualified domain name for this SAN
            - method: validation method, e.g. 'dns_cf' for Cloudflare DNS-01,
              'http' for an HTTP-01 challenge, 'webroot', etc. — see the
              pfSense ACME package for the full provider list.
            - method-specific credential/config fields, e.g. for method='dns_cf':
              either {"cf_token": "..."} (scoped API token) or
              {"cf_email": "...", "cf_key": "..."} (legacy global key).
            Example: [{"name": "app.example.com", "method": "dns_cf", "cf_token": "..."}]
            To add/remove a single domain later without resending this whole
            list, use manage_acme_certificate_domain.
        descr: Optional description
        acmeaccount: ACME account key reference name (from search_acme_account_keys)
        keylength: Key length/type (e.g., '2048', '4096', 'ec-256', 'ec-384')
        dnssleep: Seconds to sleep after publishing the DNS-01 record instead
            of acme.sh auto-detecting propagation. Without this, acme.sh polls
            public DNS-over-HTTPS resolvers (cloudflare-dns.com, dns.google,
            etc.) to check propagation — on networks that block outbound DoH
            (common DNS-hardening setups), that check can never succeed and
            the issuance hangs indefinitely with no error. Set this (e.g. 60-120)
            to skip the check and just wait a fixed time before validation.
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        cert_data: Dict = {"name": name, "a_domainlist": a_domainlist}

        if descr:
            cert_data["descr"] = sanitize_description(descr)
        if acmeaccount:
            cert_data["acmeaccount"] = acmeaccount
        if keylength:
            cert_data["keylength"] = keylength
        if dnssleep is not None:
            cert_data["dnssleep"] = dnssleep

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
@rate_limited
async def update_acme_certificate(
    certificate_id: int,
    name: Optional[str] = None,
    descr: Optional[str] = None,
    acmeaccount: Optional[str] = None,
    keylength: Optional[str] = None,
    a_domainlist: Optional[List[Dict]] = None,
    dnssleep: Optional[int] = None,
    apply_immediately: bool = True,
) -> Dict:
    """Update an existing ACME certificate entry by ID

    Args:
        certificate_id: Certificate ID (from search_acme_certificates)
        name: Certificate name
        descr: Description
        acmeaccount: ACME account key reference name
        keylength: Key length/type
        a_domainlist: Replace the certificate's full domain (SAN) validation
            list (same entry shape as create_acme_certificate). To add or
            remove a single domain without resending the whole list, use
            manage_acme_certificate_domain instead.
        dnssleep: Seconds to sleep after publishing the DNS-01 record instead
            of acme.sh auto-detecting propagation via public DoH resolvers —
            set this if issuance hangs indefinitely on a network that blocks
            outbound DNS-over-HTTPS (see create_acme_certificate for detail).
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        params = {
            "name": name,
            "descr": descr,
            "acmeaccount": acmeaccount,
            "keylength": keylength,
            "a_domainlist": a_domainlist,
            "dnssleep": dnssleep,
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
# Certificate Domains (SAN / validation methods)
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_acme_certificate_domains(
    parent_id: int,
    search_term: Optional[str] = None,
) -> Dict:
    """List the domain (SAN) validation entries configured on an ACME certificate

    The pfSense API embeds each certificate's domain list (`a_domainlist`)
    inline on the certificate object rather than exposing a standalone list
    endpoint, so this fetches the parent certificate and returns its domains.

    Args:
        parent_id: ACME certificate ID (from search_acme_certificates)
        search_term: Search in domain name (client-side filter)
    """
    client = get_api_client()
    try:
        pagination, _, _ = create_pagination(1, 1)

        result = await client.crud_list(
            "/services/acme/certificates",
            filters=[QueryFilter("id", str(parent_id))],
            pagination=pagination,
        )

        certs = result.get("data") or []
        if not certs:
            return {"success": False, "error": f"ACME certificate {parent_id} not found"}

        domains = certs[0].get("a_domainlist") or []

        if search_term:
            term_lower = search_term.lower()
            domains = [d for d in domains if field_contains(d, "name", term_lower)]

        return {
            "success": True,
            "parent_id": parent_id,
            "count": len(domains),
            "domains": domains,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search ACME certificate domains: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
@rate_limited
async def manage_acme_certificate_domain(
    action: str,
    parent_id: int,
    name: Optional[str] = None,
    method: Optional[str] = None,
    provider_fields: Optional[Dict] = None,
    domain_id: Optional[int] = None,
    apply_immediately: bool = True,
    confirm: bool = False,
) -> Dict:
    """Add or remove a domain (SAN) validation entry on an ACME certificate

    Each ACME certificate needs at least one domain entry describing how
    pfSense proves ownership to Let's Encrypt (HTTP-01, DNS-01 via a provider
    API, manual DNS, etc.) before a certificate can be issued. This manages
    entries one at a time instead of replacing the whole a_domainlist array
    (see update_acme_certificate for a full-replace).

    Args:
        action: Action to perform ('create' or 'delete')
        parent_id: ACME certificate ID (from search_acme_certificates)
        name: Fully-qualified domain name / SAN (required for create)
        method: Validation method (required for create). Common values:
            'dns_cf' (Cloudflare DNS-01), 'http' (HTTP-01), 'webroot'.
            See the pfSense ACME package for the full provider list.
        provider_fields: Method-specific credential/config fields, merged
            directly into the request. Example for method='dns_cf' with an
            API token: {"cf_token": "..."}. With a legacy global key:
            {"cf_email": "...", "cf_key": "..."}.
        domain_id: Domain entry ID (required for delete)
        apply_immediately: Whether to apply changes immediately
        confirm: Must be set to True for delete operations. Safety gate for destructive operations.
    """
    client = get_api_client()
    try:
        action_lower = action.lower()

        if action_lower == "create":
            if not name:
                return {"success": False, "error": "name is required for create action"}
            if not method:
                return {"success": False, "error": "method is required for create action"}

            domain_data: Dict = {
                "parent_id": parent_id,
                "name": name,
                "method": method,
            }
            if provider_fields:
                domain_data.update(provider_fields)

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_create("/services/acme/certificate/domain", domain_data, control)

            return {
                "success": True,
                "message": f"Domain '{name}' ({method}) added to ACME certificate {parent_id}",
                "domain": result.get("data", result),
                "applied": apply_immediately,
                "links": client.extract_links(result),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        elif action_lower == "delete":
            if domain_id is None:
                return {"success": False, "error": "domain_id is required for delete action"}

            if not confirm:
                return {
                    "success": False,
                    "error": "This is a destructive operation. Set confirm=True to proceed.",
                    "details": f"Will permanently delete domain {domain_id} from ACME certificate {parent_id}.",
                }

            control = ControlParameters(apply=apply_immediately)
            result = await client.crud_delete(
                "/services/acme/certificate/domain", domain_id, control,
                extra_data={"parent_id": parent_id},
            )

            return {
                "success": True,
                "message": f"Domain {domain_id} removed from ACME certificate {parent_id}",
                "domain_id": domain_id,
                "parent_id": parent_id,
                "applied": apply_immediately,
                "result": result.get("data", result),
                "links": client.extract_links(result),
                "note": "Object IDs have shifted after deletion. Re-query the certificate before performing further operations by ID.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}'. Must be 'create' or 'delete'.",
            }
    except Exception as e:
        logger.error(f"Failed to manage ACME certificate domain: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Certificate Issue & Renew
# ---------------------------------------------------------------------------


async def _resolve_acme_certificate_name(client, certificate_id: int) -> str:
    """Resolve an ACME certificate's numeric id to its `name`.

    The issue/renew endpoints key off the certificate's `name` field, not
    the array-index `id` used everywhere else in this API — passing `id`
    fails with "Field `certificate` is required."
    """
    pagination, _, _ = create_pagination(1, 1)
    result = await client.crud_list(
        "/services/acme/certificates",
        filters=[QueryFilter("id", str(certificate_id))],
        pagination=pagination,
    )
    certs = result.get("data") or []
    if not certs:
        raise ValueError(f"ACME certificate {certificate_id} not found")
    name = certs[0].get("name")
    if not name:
        raise ValueError(f"ACME certificate {certificate_id} has no name")
    return name


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
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
        name = await _resolve_acme_certificate_name(client, id)

        issue_data: Dict = {"certificate": name}
        control = ControlParameters(apply=True)
        result = await client.crud_create("/services/acme/certificate/issue", issue_data, control)

        return {
            "success": True,
            "message": f"ACME certificate '{name}' (id {id}) issue requested",
            "certificate_id": id,
            "certificate_name": name,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to issue ACME certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
@rate_limited
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
        name = await _resolve_acme_certificate_name(client, id)

        renew_data: Dict = {"certificate": name}
        control = ControlParameters(apply=True)
        result = await client.crud_create("/services/acme/certificate/renew", renew_data, control)

        return {
            "success": True,
            "message": f"ACME certificate '{name}' (id {id}) renewal requested",
            "certificate_id": id,
            "certificate_name": name,
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
        pagination, page, page_size = create_search_pagination(page, page_size, search_term)
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
                if field_contains(k, "name", term_lower)
                or field_contains(k, "descr", term_lower)
                or field_contains(k, "email", term_lower)
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
@rate_limited
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
@rate_limited
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
