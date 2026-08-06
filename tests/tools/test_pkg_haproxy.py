"""Unit tests for HAProxy package tools (src/tools/pkg_haproxy.py)."""

from src.tools.pkg_haproxy import (
    create_haproxy_frontend,
    manage_haproxy_frontend_address,
    manage_haproxy_frontend_certificate,
    search_haproxy_frontend_addresses,
    search_haproxy_frontend_certificates,
    update_haproxy_frontend,
)

_create_haproxy_frontend = create_haproxy_frontend
_update_haproxy_frontend = update_haproxy_frontend
_search_haproxy_frontend_addresses = search_haproxy_frontend_addresses
_manage_haproxy_frontend_address = manage_haproxy_frontend_address
_search_haproxy_frontend_certificates = search_haproxy_frontend_certificates
_manage_haproxy_frontend_certificate = manage_haproxy_frontend_certificate


# ---------------------------------------------------------------------------
# create_haproxy_frontend / update_haproxy_frontend
# Regression: the pfSense API field is `a_extaddr`, not `bind_addresses` —
# the old code sent an unknown field and silently dropped the bind address.
# ---------------------------------------------------------------------------

class TestCreateHaproxyFrontend:
    async def test_bind_addresses_sent_as_a_extaddr(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        addresses = [{"extaddr": "custom", "extaddr_custom": "192.168.1.100", "extaddr_port": "443", "extaddr_ssl": True}]
        result = await _create_haproxy_frontend(name="ha_frontend", bind_addresses=addresses)
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["a_extaddr"] == addresses
        assert "bind_addresses" not in data

    async def test_ssloffloadcert_and_ha_certificates(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _create_haproxy_frontend(
            name="ha_frontend",
            ssloffloadcert="abc123refid",
            ha_certificates=["def456refid"],
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["ssloffloadcert"] == "abc123refid"
        assert data["ha_certificates"] == ["def456refid"]

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("create failed")
        result = await _create_haproxy_frontend(name="ha_frontend")
        assert result["success"] is False


class TestUpdateHaproxyFrontend:
    async def test_bind_addresses_sent_as_a_extaddr(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        addresses = [{"extaddr": "custom", "extaddr_custom": "192.168.1.100", "extaddr_port": "443", "extaddr_ssl": True}]
        result = await _update_haproxy_frontend(frontend_id=0, bind_addresses=addresses)
        assert result["success"] is True
        assert "a_extaddr" in result["fields_updated"]
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["a_extaddr"] == addresses

    async def test_ssloffloadcert_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _update_haproxy_frontend(frontend_id=0, ssloffloadcert="abc123refid")
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["ssloffloadcert"] == "abc123refid"
        assert data["id"] == 0

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await _update_haproxy_frontend(frontend_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]


# ---------------------------------------------------------------------------
# Frontend addresses sub-resource
# ---------------------------------------------------------------------------

class TestSearchHaproxyFrontendAddresses:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [{"id": 0, "parent_id": 0, "extaddr": "custom", "extaddr_custom": "192.168.1.100", "extaddr_port": "443"}]
        }
        result = await _search_haproxy_frontend_addresses(parent_id=0)
        assert result["success"] is True
        assert result["count"] == 1
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "parent_id" and f.value == "0" for f in filters)


class TestManageHaproxyFrontendAddress:
    async def test_create_requires_extaddr(self, mock_client, mock_make_request):
        result = await _manage_haproxy_frontend_address(action="create", parent_id=0, extaddr_port="443")
        assert result["success"] is False
        assert "extaddr" in result["error"]

    async def test_create_requires_port(self, mock_client, mock_make_request):
        result = await _manage_haproxy_frontend_address(action="create", parent_id=0, extaddr="custom")
        assert result["success"] is False
        assert "extaddr_port" in result["error"]

    async def test_create_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _manage_haproxy_frontend_address(
            action="create", parent_id=0, extaddr="custom",
            extaddr_custom="192.168.1.100", extaddr_port="443", extaddr_ssl=True,
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["parent_id"] == 0
        assert data["extaddr_custom"] == "192.168.1.100"
        assert data["extaddr_ssl"] is True

    async def test_delete_requires_confirm(self, mock_client, mock_make_request):
        result = await _manage_haproxy_frontend_address(action="delete", parent_id=0, address_id=1)
        assert result["success"] is False
        assert "confirm" in result["error"].lower()

    async def test_delete_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _manage_haproxy_frontend_address(action="delete", parent_id=0, address_id=1, confirm=True)
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 1
        assert data["parent_id"] == 0


# ---------------------------------------------------------------------------
# Frontend certificates sub-resource
# ---------------------------------------------------------------------------

class TestSearchHaproxyFrontendCertificates:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [{"id": 0, "parent_id": 0, "ssl_certificate": "abc123refid"}]
        }
        result = await _search_haproxy_frontend_certificates(parent_id=0)
        assert result["success"] is True
        assert result["count"] == 1


class TestManageHaproxyFrontendCertificate:
    async def test_create_requires_ssl_certificate(self, mock_client, mock_make_request):
        result = await _manage_haproxy_frontend_certificate(action="create", parent_id=0)
        assert result["success"] is False
        assert "ssl_certificate" in result["error"]

    async def test_create_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _manage_haproxy_frontend_certificate(
            action="create", parent_id=0, ssl_certificate="abc123refid",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["parent_id"] == 0
        assert data["ssl_certificate"] == "abc123refid"

    async def test_delete_requires_confirm(self, mock_client, mock_make_request):
        result = await _manage_haproxy_frontend_certificate(action="delete", parent_id=0, certificate_id=1)
        assert result["success"] is False
        assert "confirm" in result["error"].lower()

    async def test_delete_success(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _manage_haproxy_frontend_certificate(
            action="delete", parent_id=0, certificate_id=1, confirm=True,
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 1
        assert data["parent_id"] == 0
