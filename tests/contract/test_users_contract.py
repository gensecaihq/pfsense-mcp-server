"""Contract tests for the user-group and LDAP auth-server wire fixes.

Before these fixes: groups sent `descr` (upstream `description`); LDAP auth
servers sent generic `port`/`transport`/`scope`/`basedn`/`authcn` with a
tcp/ssl/starttls transport vocabulary, none of which the API recognizes — so
LDAP servers and group descriptions could never be set.
"""
from src.tools.users import (
    create_auth_server,
    create_group,
    update_auth_server,
    update_group,
)
from tests.contract.schema import assert_payload_valid, capture_call


class TestGroups:
    async def test_create_uses_description_and_member(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_group(
            name="admins", descr="Administrators", member=["alice", "bob"],
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/user/group"
        assert data["description"] == "Administrators" and "descr" not in data
        assert data["member"] == ["alice", "bob"]

    async def test_update_maps_descr_to_description(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_group(group_id=1, descr="Updated")
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["description"] == "Updated" and "descr" not in data


class TestLdapAuthServer:
    async def test_create_uses_ldap_field_names_and_urltype(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        # Multi-container LDAP authcn (semicolon-separated) — must NOT trip the
        # sanitizer any more (the command-chaining rule was removed in v1.2).
        result = await create_auth_server(
            name="ad", type="ldap", host="dc.example.com", port=636,
            transport="ssl", scope="subtree", basedn="dc=example,dc=com",
            authcn="CN=Users;DC=example,DC=com", ldap_bindpw="secret",
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/user/auth_server"
        assert data["ldap_port"] == "636"  # PortField is string-typed upstream
        assert data["ldap_urltype"] == "SSL/TLS Encrypted"
        assert data["ldap_scope"] == "subtree"
        assert data["ldap_basedn"] == "dc=example,dc=com"
        assert data["ldap_authcn"] == "CN=Users;DC=example,DC=com"
        for stale in ("transport", "scope", "basedn", "authcn", "port"):
            assert stale not in data

    async def test_starttls_maps_to_url_type(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await create_auth_server(
            name="ad", type="ldap", host="h", transport="starttls", ldap_bindpw="x",
        )
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["ldap_urltype"] == "STARTTLS Encrypt"

    async def test_update_maps_ldap_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_auth_server(
            auth_server_id=2, transport="tcp", scope="one", basedn="dc=x", authcn="CN=x",
        )
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["ldap_urltype"] == "Standard TCP"
        assert data["ldap_scope"] == "one"
        assert data["ldap_basedn"] == "dc=x"
        assert data["ldap_authcn"] == "CN=x"

    async def test_radius_path_still_valid(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_auth_server(
            name="rad", type="radius", host="r.example.com",
            radius_secret="s", radius_auth_port=1812,
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["radius_secret"] == "s" and data["radius_auth_port"] == "1812"
