"""TLS verification and custom CA bundle handling in the API client.

pfSense almost always presents a certificate from its own private CA. Python
does not read the OS trust store, so the path of least resistance has been
VERIFY_SSL=false — which stops authenticating the firewall and puts the API
credential on a connection nobody checked. These tests pin the alternative:
a CA bundle keeps verification on, and a bad bundle fails at startup instead
of quietly downgrading.
"""
import ssl
from unittest.mock import patch

import pytest

from src.client import EnhancedPfSenseAPIClient
from src.models import AuthMethod

# A throwaway self-signed CA, generated for this suite only. It never
# authenticates anything — ssl.create_default_context() just has to be able to
# parse it, which a hand-written placeholder cannot do.
TEST_CA_PEM = """-----BEGIN CERTIFICATE-----
MIIDHTCCAgWgAwIBAgIUOqJS5hf8t8D0HI9BTrHwDwtVIakwDQYJKoZIhvcNAQEL
BQAwHjEcMBoGA1UEAwwTcGZzZW5zZS1tY3AtdGVzdC1jYTAeFw0yNjA4MTIxOTI3
MjZaFw0zNjA4MDkxOTI3MjZaMB4xHDAaBgNVBAMME3Bmc2Vuc2UtbWNwLXRlc3Qt
Y2EwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCjU7az6UVAltSORaJT
FhF66FCbiXESTl2d6X4XSzKzxQvj8lnH5BZVs7XNYHnE8rIgi6HQDWkDphmZuAsj
jP45opaRQFdO98johbghZQLeTV/pJaV2pTByygea7NvPzRUGmleEsjV2K72MQuJT
/NzApoCHF9XY29fHqM4kXL0J/QNAusOF0qjkDcRDnDQcy3exhyQ2W2LI8nBMtJVN
tzAlnnwEnOxMMImhBK4xIpUUCX6TPmvPvJ9u13ieiNYovpV/ZNKuZUnNHWyH/TBT
s1e4a9wyuE4MwwaYcHNKMKJLLjKYjtsRBww2Ei4YzLXwBpb3rNZRrkIehTYPS4F3
cgBrAgMBAAGjUzBRMB0GA1UdDgQWBBQVtf3thTo8LnRw9c9/rgv6UG3RKzAfBgNV
HSMEGDAWgBQVtf3thTo8LnRw9c9/rgv6UG3RKzAPBgNVHRMBAf8EBTADAQH/MA0G
CSqGSIb3DQEBCwUAA4IBAQBIl+goI3kFhMSCuNyLmsM7srglzYV4AWQCr5P6VKZd
gb2k/xKhXrWfTCDm+SCEYoJAbJOIVUGF63jITFlv2qqAcFav/ht63Ef4+P6a3TZJ
/JeVuWGFPAPRrcywdLNQx2AMq/RCDxi19rjSrE7tg/Gp/yK1Yt7QrFvszwVGaaMe
af23yYFpCXJRHi+rxvLj+mIRjwGq7KNMVzMal84YgylbkXkpq13mQaccIMaVsY9j
b1Uihd4ITdzHg66MrCOp4kG2q8EvN89ALqHG0UOIPx7rrBKzPMI/UhpDVUtVOqJr
kNfW/O2bvcT8R0wcjB6w93hEN128/V8TpvWPFX6wMhha
-----END CERTIFICATE-----
"""


@pytest.fixture
def real_ca_file(tmp_path):
    """A PEM that ssl.create_default_context() will actually load."""
    path = tmp_path / "pfsense-ca.pem"
    path.write_text(TEST_CA_PEM)
    return path


def _client(**kwargs):
    return EnhancedPfSenseAPIClient(
        host="https://192.0.2.1",
        auth_method=AuthMethod.API_KEY,
        api_key="test-key",
        **kwargs,
    )


class TestResolveVerify:
    def test_defaults_to_verifying(self):
        assert _client()._verify is True

    def test_explicit_opt_out_is_honored(self):
        assert _client(verify_ssl=False)._verify is False

    def test_ca_file_builds_a_server_auth_context(self, tmp_path, real_ca_file):
        client = _client(ca_file=str(real_ca_file))
        ctx = client._verify

        assert isinstance(ctx, ssl.SSLContext)
        # Secure defaults must survive: a context that skips these would
        # verify nothing while looking like it does.
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_ca_file_is_expanded(self, real_ca_file, monkeypatch):
        monkeypatch.setenv("HOME", str(real_ca_file.parent))
        client = _client(ca_file=f"~/{real_ca_file.name}")
        assert isinstance(client._verify, ssl.SSLContext)

    def test_missing_ca_file_fails_closed(self, tmp_path):
        with pytest.raises(ValueError, match="CA bundle not found"):
            _client(ca_file=str(tmp_path / "absent.pem"))

    def test_directory_is_not_accepted_as_a_bundle(self, tmp_path):
        with pytest.raises(ValueError, match="CA bundle not found"):
            _client(ca_file=str(tmp_path))

    def test_unparseable_ca_file_fails_closed(self, tmp_path):
        bad = tmp_path / "bad.pem"
        bad.write_text("this is not a certificate\n")
        with pytest.raises(ValueError, match="could not be loaded"):
            _client(ca_file=str(bad))

    def test_load_failure_does_not_leak_file_contents(self, tmp_path):
        secret = "SUPER-SECRET-KEY-MATERIAL"
        bad = tmp_path / "bad.pem"
        bad.write_text(f"-----BEGIN PRIVATE KEY-----\n{secret}\n")
        with pytest.raises(ValueError) as exc:
            _client(ca_file=str(bad))
        assert secret not in str(exc.value)

    def test_opt_out_wins_over_ca_file_but_warns(self, real_ca_file, caplog):
        with caplog.at_level("WARNING"):
            client = _client(verify_ssl=False, ca_file=str(real_ca_file))
        assert client._verify is False
        assert "ignored" in caplog.text
        assert "NOT" in caplog.text


class TestVerifyReachesHttpx:
    def _captured_verify(self, **kwargs):
        client = _client(**kwargs)
        with patch("src.client.httpx.AsyncClient") as ac:
            client._ensure_client()
        return ac.call_args.kwargs["verify"]

    def test_context_is_passed_through(self, real_ca_file):
        verify = self._captured_verify(ca_file=str(real_ca_file))
        assert isinstance(verify, ssl.SSLContext)

    def test_bool_is_passed_through(self):
        assert self._captured_verify() is True
        assert self._captured_verify(verify_ssl=False) is False


class TestConnectionErrorGuidance:
    async def test_tls_failure_points_at_the_ca_file_first(self):
        """The old hint told operators to disable verification. It shouldn't."""
        client = _client()
        with patch.object(client, "_make_request", side_effect=Exception("SSL: CERTIFICATE_VERIFY_FAILED")):
            result = await client.test_connection()

        assert result["connected"] is False
        error = result["error"]
        assert "PFSENSE_CA_FILE" in error
        assert error.index("PFSENSE_CA_FILE") < error.index("VERIFY_SSL=false")
