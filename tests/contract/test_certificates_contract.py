"""Contract tests for the certificate/CA wire fixes.

Before these fixes: import sent `cert` (upstream `crt`) so it 400'd; internal
generation was POSTed to the import endpoint (wrong fields dropped); renew and
PKCS#12 export sent the array-index `id` instead of the required `certref`.
Each test drives the real tool and asserts the payload matches the v2.10.0
contract.
"""
from src.tools.certificates import (
    create_certificate,
    create_certificate_authority,
    export_certificate_pkcs12,
    generate_certificate,
    renew_certificate,
    update_certificate,
    update_certificate_authority,
)
from tests.contract.schema import assert_payload_valid, capture_call


class TestCreateCertificate:
    async def test_import_uses_crt_and_import_endpoint(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_certificate(
            method="import", descr="web", cert="-----PEM-----", prv="-----KEY-----",
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        method, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/system/certificate"
        assert data["crt"] == "-----PEM-----" and "cert" not in data and "method" not in data

    async def test_internal_routes_to_generate_endpoint(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_certificate(
            method="internal", descr="gen", keytype="RSA", keylen=2048,
            digest_alg="sha256", dn_commonname="host.example.com", caref="ca1",
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/system/certificate/generate"
        assert "method" not in data

    async def test_import_without_key_rejected(self, mock_client, mock_make_request):
        result = await create_certificate(method="import", descr="x", cert="pem")
        assert result["success"] is False

    async def test_ecdsa_sends_ecname(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await create_certificate(
            method="internal", descr="ec", keytype="ECDSA", ecname="prime256v1",
            digest_alg="sha256", dn_commonname="ec.example.com", caref="ca1",
        )
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["ecname"] == "prime256v1"


class TestUpdateCertificate:
    async def test_uses_crt(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_certificate(certificate_id=2, cert="-----PEM-----")
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["crt"] == "-----PEM-----" and "cert" not in data


class TestCertificateAuthority:
    async def test_import_uses_crt(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_certificate_authority(method="import", descr="ca", cert="-----PEM-----")
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/system/certificate_authority"
        assert data["crt"] == "-----PEM-----" and "cert" not in data

    async def test_internal_routes_to_generate(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await create_certificate_authority(
            method="internal", descr="ca", keytype="RSA", keylen=2048,
            digest_alg="sha256", dn_commonname="Root CA",
        )
        assert_payload_valid(mock_make_request)
        _, endpoint, _ = capture_call(mock_make_request)
        assert endpoint == "/system/certificate_authority/generate"

    async def test_update_uses_crt(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_certificate_authority(ca_id=1, cert="-----PEM-----")
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["crt"] == "-----PEM-----" and "cert" not in data


class TestGenerateCertificate:
    async def test_no_method_rsa_sends_keylen(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await generate_certificate(descr="g", caref="ca1", dn_commonname="h", keytype="RSA")
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert "method" not in data and data["keylen"] == 2048

    async def test_ecdsa_sends_ecname_not_keylen(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await generate_certificate(
            descr="g", caref="ca1", dn_commonname="h", keytype="ECDSA", ecname="secp384r1",
        )
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["ecname"] == "secp384r1" and "keylen" not in data


class TestRenewAndExportUseCertref:
    async def test_renew_uses_certref(self, mock_client, mock_make_request):
        # GET (refid lookup) then POST both hit the mock; the last call is POST.
        mock_make_request.return_value = {"data": [{"id": 5, "refid": "abc123"}]}
        result = await renew_certificate(certificate_id=5)
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/system/certificate/renew"
        assert data["certref"] == "abc123" and "id" not in data

    async def test_pkcs12_uses_certref(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": [{"id": 5, "refid": "abc123"}]}
        result = await export_certificate_pkcs12(certificate_id=5, passphrase="secret")
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, _, data = capture_call(mock_make_request)
        assert data["certref"] == "abc123" and data["passphrase"] == "secret"
