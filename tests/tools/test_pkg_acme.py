"""Unit tests for ACME package tools (src/tools/pkg_acme.py)."""

from src.tools.pkg_acme import (
    create_acme_certificate,
    issue_acme_certificate,
    manage_acme_certificate_domain,
    renew_acme_certificate,
    search_acme_certificate_domains,
    update_acme_certificate,
)

_create_acme_certificate = create_acme_certificate
_update_acme_certificate = update_acme_certificate
_search_acme_certificate_domains = search_acme_certificate_domains
_manage_acme_certificate_domain = manage_acme_certificate_domain
_issue_acme_certificate = issue_acme_certificate
_renew_acme_certificate = renew_acme_certificate


# ---------------------------------------------------------------------------
# create_acme_certificate — regression test for missing a_domainlist
# ---------------------------------------------------------------------------

class TestCreateAcmeCertificate:
    async def test_sends_a_domainlist(self, mock_client, mock_make_request):
        """Regression: the pfSense API rejects certs with no a_domainlist
        ("Field `a_domainlist` is required"). The tool must send it."""
        mock_make_request.return_value = {"data": {"id": 0}}
        domains = [{"name": "ha.example.com", "method": "dns_cf", "cf_token": "secret-token"}]
        result = await _create_acme_certificate(
            name="ha_cert", a_domainlist=domains, acmeaccount="LE Key Prod",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["a_domainlist"] == domains
        assert data["name"] == "ha_cert"
        assert data["acmeaccount"] == "LE Key Prod"

    async def test_dnssleep(self, mock_client, mock_make_request):
        """dnssleep skips acme.sh's own DoH-based propagation check, which
        hangs forever on networks that block outbound DNS-over-HTTPS."""
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _create_acme_certificate(
            name="ha_cert",
            a_domainlist=[{"name": "ha.example.com", "method": "dns_cf"}],
            dnssleep=120,
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["dnssleep"] == 120

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("Field `a_domainlist` is required.")
        result = await _create_acme_certificate(name="ha_cert", a_domainlist=[])
        assert result["success"] is False
        assert "a_domainlist" in result["error"]


# ---------------------------------------------------------------------------
# update_acme_certificate
# ---------------------------------------------------------------------------

class TestUpdateAcmeCertificate:
    async def test_replaces_domain_list(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        domains = [{"name": "new.example.com", "method": "http"}]
        result = await _update_acme_certificate(certificate_id=0, a_domainlist=domains)
        assert result["success"] is True
        assert "a_domainlist" in result["fields_updated"]
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["a_domainlist"] == domains

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await _update_acme_certificate(certificate_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]

    async def test_dnssleep(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _update_acme_certificate(certificate_id=0, dnssleep=120)
        assert result["success"] is True
        assert "dnssleep" in result["fields_updated"]
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["dnssleep"] == 120


# ---------------------------------------------------------------------------
# search_acme_certificate_domains
# ---------------------------------------------------------------------------

class TestSearchAcmeCertificateDomains:
    async def test_returns_embedded_domains(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [
                {
                    "id": 0,
                    "name": "ha_cert",
                    "a_domainlist": [
                        {"name": "ha.example.com", "method": "dns_cf"},
                        {"name": "other.example.com", "method": "http"},
                    ],
                }
            ]
        }
        result = await _search_acme_certificate_domains(parent_id=0)
        assert result["success"] is True
        assert result["count"] == 2
        # parent_id must be filtered via an "id" query filter, not a body param
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "id" and f.value == "0" for f in filters)

    async def test_search_term_filters_by_name(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [
                {
                    "id": 0,
                    "a_domainlist": [
                        {"name": "ha.example.com", "method": "dns_cf"},
                        {"name": "other.example.com", "method": "http"},
                    ],
                }
            ]
        }
        result = await _search_acme_certificate_domains(parent_id=0, search_term="ha.")
        assert result["count"] == 1
        assert result["domains"][0]["name"] == "ha.example.com"

    async def test_certificate_not_found(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        result = await _search_acme_certificate_domains(parent_id=99)
        assert result["success"] is False
        assert "not found" in result["error"]

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("boom")
        result = await _search_acme_certificate_domains(parent_id=0)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# manage_acme_certificate_domain
# ---------------------------------------------------------------------------

class TestManageAcmeCertificateDomain:
    async def test_create_requires_name(self, mock_client, mock_make_request):
        result = await _manage_acme_certificate_domain(action="create", parent_id=0, method="dns_cf")
        assert result["success"] is False
        assert "name" in result["error"]

    async def test_create_requires_method(self, mock_client, mock_make_request):
        result = await _manage_acme_certificate_domain(action="create", parent_id=0, name="ha.example.com")
        assert result["success"] is False
        assert "method" in result["error"]

    async def test_create_merges_provider_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _manage_acme_certificate_domain(
            action="create",
            parent_id=5,
            name="ha.example.com",
            method="dns_cf",
            provider_fields={"cf_token": "secret-token"},
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["parent_id"] == 5
        assert data["name"] == "ha.example.com"
        assert data["method"] == "dns_cf"
        assert data["cf_token"] == "secret-token"

    async def test_delete_requires_confirm(self, mock_client, mock_make_request):
        result = await _manage_acme_certificate_domain(action="delete", parent_id=5, domain_id=1)
        assert result["success"] is False
        assert "confirm" in result["error"].lower()

    async def test_delete_requires_domain_id(self, mock_client, mock_make_request):
        result = await _manage_acme_certificate_domain(action="delete", parent_id=5, confirm=True)
        assert result["success"] is False
        assert "domain_id" in result["error"]

    async def test_delete_passes_parent_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _manage_acme_certificate_domain(
            action="delete", parent_id=5, domain_id=1, confirm=True,
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 1
        assert data["parent_id"] == 5

    async def test_invalid_action(self, mock_client, mock_make_request):
        result = await _manage_acme_certificate_domain(action="frobnicate", parent_id=5)
        assert result["success"] is False
        assert "Invalid action" in result["error"]

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("boom")
        result = await _manage_acme_certificate_domain(
            action="create", parent_id=0, name="ha.example.com", method="http",
        )
        assert result["success"] is False


# ---------------------------------------------------------------------------
# issue_acme_certificate / renew_acme_certificate
# Regression: the pfSense API keys these off the certificate's `name`, not
# its numeric `id` — sending `id` fails with "Field `certificate` is required."
# ---------------------------------------------------------------------------

class TestIssueAcmeCertificate:
    async def test_resolves_id_to_name(self, mock_client, mock_make_request):
        mock_make_request.side_effect = [
            {"data": [{"id": 0, "name": "ha_nagyfamily_net"}]},  # name lookup
            {"data": {"status": "pending"}},  # the issue POST
        ]
        result = await _issue_acme_certificate(id=0)
        assert result["success"] is True
        assert result["certificate_name"] == "ha_nagyfamily_net"
        issue_call = mock_make_request.call_args_list[1]
        data = issue_call.kwargs.get("data") or issue_call[1].get("data")
        assert data["certificate"] == "ha_nagyfamily_net"
        assert "id" not in data

    async def test_certificate_not_found(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        result = await _issue_acme_certificate(id=99)
        assert result["success"] is False
        assert "not found" in result["error"]

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("boom")
        result = await _issue_acme_certificate(id=0)
        assert result["success"] is False


class TestRenewAcmeCertificate:
    async def test_resolves_id_to_name(self, mock_client, mock_make_request):
        mock_make_request.side_effect = [
            {"data": [{"id": 0, "name": "ha_nagyfamily_net"}]},  # name lookup
            {"data": {"status": "pending"}},  # the renew POST
        ]
        result = await _renew_acme_certificate(id=0)
        assert result["success"] is True
        assert result["certificate_name"] == "ha_nagyfamily_net"
        renew_call = mock_make_request.call_args_list[1]
        data = renew_call.kwargs.get("data") or renew_call[1].get("data")
        assert data["certificate"] == "ha_nagyfamily_net"
        assert "id" not in data

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("boom")
        result = await _renew_acme_certificate(id=0)
        assert result["success"] is False
