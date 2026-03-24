"""Certificate and PKI management tools for pfSense MCP server."""

from datetime import datetime, timezone
from typing import Dict, Optional

from ..helpers import create_default_sort, create_pagination, sanitize_description
from ..models import ControlParameters, QueryFilter
from ..server import get_api_client, logger, mcp
from mcp.types import ToolAnnotations


# ---------------------------------------------------------------------------
# Certificates
# ---------------------------------------------------------------------------


from ..guardrails import guarded
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_certificates(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict:
    """Search certificates configured on pfSense with optional filtering

    Args:
        search_term: Search in certificate descriptions/common names
        page: Page number for pagination
        page_size: Number of results per page
    """
    client = get_api_client()
    try:
        filters = []
        if search_term:
            filters.append(QueryFilter("descr", search_term, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort("descr")

        result = await client._make_request(
            "GET", "/system/certificates",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(result.get("data") or []),
            "certificates": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search certificates: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_certificate(
    method: str,
    descr: str,
    cert: Optional[str] = None,
    prv: Optional[str] = None,
    keytype: Optional[str] = None,
    keylen: Optional[int] = None,
    digest_alg: Optional[str] = None,
    lifetime: Optional[int] = None,
    dn_commonname: Optional[str] = None,
    dn_country: Optional[str] = None,
    dn_state: Optional[str] = None,
    dn_city: Optional[str] = None,
    dn_organization: Optional[str] = None,
    type: Optional[str] = None,
    caref: Optional[str] = None,
) -> Dict:
    """Create or import a certificate on pfSense

    Args:
        method: Creation method — "import" to import existing, "internal" to generate internally
        descr: Descriptive name for the certificate
        cert: PEM-encoded certificate data (required for import)
        prv: PEM-encoded private key (required for import)
        keytype: Key type — "RSA" or "ECDSA" (for internal generation)
        keylen: Key length in bits, e.g. 2048, 4096 (for RSA) or 256, 384 (for ECDSA)
        digest_alg: Digest algorithm — sha256, sha384, sha512
        lifetime: Certificate lifetime in days
        dn_commonname: Distinguished name — Common Name
        dn_country: Distinguished name — Country code (2 letter)
        dn_state: Distinguished name — State or Province
        dn_city: Distinguished name — City or Locality
        dn_organization: Distinguished name — Organization
        type: Certificate type — "server", "user", etc.
        caref: Reference ID of the signing CA (for internal generation)
    """
    client = get_api_client()
    try:
        cert_data: Dict = {
            "method": method,
            "descr": sanitize_description(descr),
        }

        # Import fields
        if cert:
            cert_data["cert"] = cert
        if prv:
            cert_data["prv"] = prv

        # Generation fields
        optional_fields = {
            "keytype": keytype,
            "keylen": keylen,
            "digest_alg": digest_alg,
            "lifetime": lifetime,
            "dn_commonname": dn_commonname,
            "dn_country": dn_country,
            "dn_state": dn_state,
            "dn_city": dn_city,
            "dn_organization": dn_organization,
            "type": type,
            "caref": caref,
        }
        for field_name, value in optional_fields.items():
            if value is not None:
                cert_data[field_name] = value

        result = await client._make_request(
            "POST", "/system/certificate",
            data=cert_data,
        )

        return {
            "success": True,
            "message": f"Certificate '{descr}' created via method '{method}'",
            "certificate": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_certificate(
    certificate_id: int,
    descr: Optional[str] = None,
    cert: Optional[str] = None,
    prv: Optional[str] = None,
) -> Dict:
    """Update an existing certificate by ID (idempotent)

    Args:
        certificate_id: Certificate ID (array index from search_certificates)
        descr: Updated descriptive name
        cert: Updated PEM-encoded certificate data
        prv: Updated PEM-encoded private key
    """
    client = get_api_client()
    try:
        updates: Dict = {"id": certificate_id}

        if descr is not None:
            updates["descr"] = sanitize_description(descr)
        if cert is not None:
            updates["cert"] = cert
        if prv is not None:
            updates["prv"] = prv

        if len(updates) <= 1:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        result = await client._make_request(
            "PATCH", "/system/certificate",
            data=updates,
        )

        return {
            "success": True,
            "message": f"Certificate {certificate_id} updated",
            "certificate_id": certificate_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_certificate(
    certificate_id: int,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a certificate by ID. WARNING: This is irreversible.

    Args:
        certificate_id: Certificate ID (array index from search_certificates)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        result = await client._make_request(
            "DELETE", "/system/certificate",
            data={"id": certificate_id},
        )

        return {
            "success": True,
            "message": f"Certificate {certificate_id} deleted",
            "certificate_id": certificate_id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query certificates before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def generate_certificate(
    descr: str,
    caref: str,
    dn_commonname: str,
    method: str = "internal",
    keytype: str = "RSA",
    keylen: int = 2048,
    digest_alg: str = "sha256",
    lifetime: int = 3650,
    type: str = "server",
) -> Dict:
    """Generate a new certificate signed by an existing CA on pfSense

    Args:
        descr: Descriptive name for the certificate
        caref: Reference ID of the signing Certificate Authority
        dn_commonname: Common Name for the certificate (e.g., "vpn.example.com")
        method: Generation method (default: "internal")
        keytype: Key type — "RSA" or "ECDSA"
        keylen: Key length in bits (2048, 4096 for RSA; 256, 384 for ECDSA)
        digest_alg: Digest algorithm — sha256, sha384, sha512
        lifetime: Certificate lifetime in days (default: 3650 = ~10 years)
        type: Certificate type — "server" or "user"
    """
    client = get_api_client()
    try:
        gen_data = {
            "method": method,
            "descr": sanitize_description(descr),
            "caref": caref,
            "keytype": keytype,
            "keylen": keylen,
            "digest_alg": digest_alg,
            "lifetime": lifetime,
            "dn_commonname": dn_commonname,
            "type": type,
        }

        result = await client._make_request(
            "POST", "/system/certificate/generate",
            data=gen_data,
        )

        return {
            "success": True,
            "message": f"Certificate '{descr}' generated (signed by CA '{caref}')",
            "certificate": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to generate certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def renew_certificate(
    certificate_id: int,
) -> Dict:
    """Renew an existing certificate by ID

    Args:
        certificate_id: Certificate ID (array index from search_certificates)
    """
    client = get_api_client()
    try:
        result = await client._make_request(
            "POST", "/system/certificate/renew",
            data={"id": certificate_id},
        )

        return {
            "success": True,
            "message": f"Certificate {certificate_id} renewed",
            "certificate_id": certificate_id,
            "certificate": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to renew certificate: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def export_certificate_pkcs12(
    certificate_id: int,
    passphrase: Optional[str] = None,
) -> Dict:
    """Export a certificate in PKCS#12 format

    Args:
        certificate_id: Certificate ID (array index from search_certificates)
        passphrase: Optional passphrase to protect the PKCS#12 export
    """
    client = get_api_client()
    try:
        export_data: Dict = {"id": certificate_id}
        if passphrase is not None:
            export_data["passphrase"] = passphrase

        result = await client._make_request(
            "POST", "/system/certificate/pkcs12/export",
            data=export_data,
        )

        return {
            "success": True,
            "message": f"Certificate {certificate_id} exported as PKCS#12",
            "certificate_id": certificate_id,
            "export": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to export certificate as PKCS#12: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Certificate Authorities
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_certificate_authorities(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict:
    """Search Certificate Authorities (CAs) configured on pfSense

    Args:
        search_term: Search in CA descriptions/common names
        page: Page number for pagination
        page_size: Number of results per page
    """
    client = get_api_client()
    try:
        filters = []
        if search_term:
            filters.append(QueryFilter("descr", search_term, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort("descr")

        result = await client._make_request(
            "GET", "/system/certificate_authorities",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(result.get("data") or []),
            "certificate_authorities": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search certificate authorities: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_certificate_authority(
    method: str,
    descr: str,
    cert: Optional[str] = None,
    prv: Optional[str] = None,
    keytype: Optional[str] = None,
    keylen: Optional[int] = None,
    digest_alg: Optional[str] = None,
    lifetime: Optional[int] = None,
    dn_commonname: Optional[str] = None,
    dn_country: Optional[str] = None,
    dn_state: Optional[str] = None,
    dn_city: Optional[str] = None,
    dn_organization: Optional[str] = None,
) -> Dict:
    """Create or import a Certificate Authority on pfSense

    Args:
        method: Creation method — "import" to import existing, "internal" to generate internally
        descr: Descriptive name for the CA
        cert: PEM-encoded CA certificate data (required for import)
        prv: PEM-encoded CA private key (required for import)
        keytype: Key type — "RSA" or "ECDSA" (for internal generation)
        keylen: Key length in bits, e.g. 2048, 4096 (for RSA) or 256, 384 (for ECDSA)
        digest_alg: Digest algorithm — sha256, sha384, sha512
        lifetime: CA certificate lifetime in days
        dn_commonname: Distinguished name — Common Name
        dn_country: Distinguished name — Country code (2 letter)
        dn_state: Distinguished name — State or Province
        dn_city: Distinguished name — City or Locality
        dn_organization: Distinguished name — Organization
    """
    client = get_api_client()
    try:
        ca_data: Dict = {
            "method": method,
            "descr": sanitize_description(descr),
        }

        # Import fields
        if cert:
            ca_data["cert"] = cert
        if prv:
            ca_data["prv"] = prv

        # Generation fields
        optional_fields = {
            "keytype": keytype,
            "keylen": keylen,
            "digest_alg": digest_alg,
            "lifetime": lifetime,
            "dn_commonname": dn_commonname,
            "dn_country": dn_country,
            "dn_state": dn_state,
            "dn_city": dn_city,
            "dn_organization": dn_organization,
        }
        for field_name, value in optional_fields.items():
            if value is not None:
                ca_data[field_name] = value

        result = await client._make_request(
            "POST", "/system/certificate_authority",
            data=ca_data,
        )

        return {
            "success": True,
            "message": f"Certificate Authority '{descr}' created via method '{method}'",
            "certificate_authority": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create certificate authority: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_certificate_authority(
    ca_id: int,
    descr: Optional[str] = None,
    cert: Optional[str] = None,
    prv: Optional[str] = None,
) -> Dict:
    """Update an existing Certificate Authority by ID (idempotent)

    Args:
        ca_id: Certificate Authority ID (array index from search_certificate_authorities)
        descr: Updated descriptive name
        cert: Updated PEM-encoded CA certificate data
        prv: Updated PEM-encoded CA private key
    """
    client = get_api_client()
    try:
        updates: Dict = {"id": ca_id}

        if descr is not None:
            updates["descr"] = sanitize_description(descr)
        if cert is not None:
            updates["cert"] = cert
        if prv is not None:
            updates["prv"] = prv

        if len(updates) <= 1:
            return {"success": False, "error": "No fields to update - provide at least one field"}

        result = await client._make_request(
            "PATCH", "/system/certificate_authority",
            data=updates,
        )

        return {
            "success": True,
            "message": f"Certificate Authority {ca_id} updated",
            "ca_id": ca_id,
            "fields_updated": [k for k in updates.keys() if k != "id"],
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update certificate authority: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_certificate_authority(
    ca_id: int,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a Certificate Authority by ID. WARNING: This is irreversible.

    Args:
        ca_id: Certificate Authority ID (array index from search_certificate_authorities)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        result = await client._make_request(
            "DELETE", "/system/certificate_authority",
            data={"id": ca_id},
        )

        return {
            "success": True,
            "message": f"Certificate Authority {ca_id} deleted",
            "ca_id": ca_id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query certificate authorities before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete certificate authority: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Certificate Revocation Lists (CRLs)
# ---------------------------------------------------------------------------


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
async def search_crls(
    search_term: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict:
    """Search Certificate Revocation Lists (CRLs) configured on pfSense

    Args:
        search_term: Search in CRL descriptions
        page: Page number for pagination
        page_size: Number of results per page
    """
    client = get_api_client()
    try:
        filters = []
        if search_term:
            filters.append(QueryFilter("descr", search_term, "contains"))

        pagination, page, page_size = create_pagination(page, page_size)
        sort = create_default_sort("descr")

        result = await client._make_request(
            "GET", "/system/crls",
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination,
        )

        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {"search_term": search_term},
            "count": len(result.get("data") or []),
            "crls": result.get("data") or [],
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to search CRLs: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
async def create_crl(
    caref: str,
    descr: str,
    method: str = "internal",
    lifetime: Optional[int] = None,
) -> Dict:
    """Create a Certificate Revocation List (CRL) on pfSense

    Args:
        caref: Reference ID of the Certificate Authority this CRL belongs to
        descr: Descriptive name for the CRL
        method: Creation method (default: "internal")
        lifetime: CRL lifetime in days
    """
    client = get_api_client()
    try:
        crl_data: Dict = {
            "caref": caref,
            "descr": sanitize_description(descr),
            "method": method,
        }

        if lifetime is not None:
            crl_data["lifetime"] = lifetime

        result = await client._make_request(
            "POST", "/system/crl",
            data=crl_data,
        )

        return {
            "success": True,
            "message": f"CRL '{descr}' created for CA '{caref}'",
            "crl": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to create CRL: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def update_crl(
    crl_id: int,
    descr: Optional[str] = None,
    lifetime: Optional[int] = None,
) -> Dict:
    """Update a Certificate Revocation List (CRL) by ID

    Args:
        crl_id: CRL ID (array index from search_crls)
        descr: Description
        lifetime: CRL lifetime in days
    """
    client = get_api_client()
    try:
        updates = {}
        if descr is not None:
            updates["descr"] = sanitize_description(descr)
        if lifetime is not None:
            updates["lifetime"] = lifetime

        if not updates:
            return {"success": False, "error": "No fields to update — provide at least one field"}

        result = await client._make_request(
            "PATCH", "/system/crl",
            data={**updates, "id": crl_id},
        )

        return {
            "success": True,
            "message": f"CRL {crl_id} updated",
            "crl_id": crl_id,
            "fields_updated": list(updates.keys()),
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to update CRL: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
@guarded
async def delete_crl(
    crl_id: int,
    confirm: bool = False,
    dry_run: bool = False,
) -> Dict:
    """Delete a Certificate Revocation List (CRL) by ID. WARNING: This is irreversible.

    Args:
        crl_id: CRL ID (array index from search_crls)
        confirm: Must be set to True to execute. Safety gate for destructive operations.
        dry_run: If True, preview the operation without executing.
    """
    client = get_api_client()
    try:
        result = await client._make_request(
            "DELETE", "/system/crl",
            data={"id": crl_id},
        )

        return {
            "success": True,
            "message": f"CRL {crl_id} deleted",
            "crl_id": crl_id,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "note": "Object IDs have shifted after deletion. Re-query CRLs before performing further operations by ID.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to delete CRL: {e}")
        return {"success": False, "error": str(e)}
