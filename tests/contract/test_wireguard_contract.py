"""Contract tests for the WireGuard wire fixes.

Before these fixes: peers sent `keepalive` (upstream `persistentkeepalive`),
`tun` as an array-index id (upstream references the tunnel by name), and
`port`/`listenport` as ints (upstream PortField is string-typed); new peers were
also created without `enabled`, which defaults to false upstream.
"""
from src.tools.vpn_wireguard import (
    create_wireguard_peer,
    create_wireguard_tunnel,
    manage_wireguard_peer_allowed_ip,
    update_wireguard_peer,
    update_wireguard_tunnel,
)
from tests.contract.schema import assert_payload_valid, capture_call


class TestTunnel:
    async def test_create_listenport_is_string(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_wireguard_tunnel(
            name="tun_wg0", listenport=51820, privatekey="KEY=",
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, _, data = capture_call(mock_make_request)
        assert data["listenport"] == "51820"

    async def test_update_listenport_is_string(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_wireguard_tunnel(tunnel_id=1, listenport=51821)
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["listenport"] == "51821"


class TestPeer:
    async def test_create_uses_persistentkeepalive_and_string_port(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_wireguard_peer(
            tun="tun_wg0", publickey="PUB=", endpoint="vpn.example.com",
            port=51820, keepalive=25,
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, _, data = capture_call(mock_make_request)
        assert data["persistentkeepalive"] == 25 and "keepalive" not in data
        assert data["port"] == "51820"
        assert data["tun"] == "tun_wg0"
        assert data["enabled"] is True  # sent so the peer isn't created disabled

    async def test_update_maps_keepalive_and_port(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_wireguard_peer(peer_id=3, keepalive=30, port=51830, enabled=False)
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["persistentkeepalive"] == 30 and "keepalive" not in data
        assert data["port"] == "51830"
        assert data["enabled"] is False


class TestPeerAllowedIP:
    """`mask` is required on create and typed as an integer separate from
    `address`, so a CIDR string in `address` alone never carries the prefix."""

    async def test_create_splits_cidr_into_address_and_mask(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await manage_wireguard_peer_allowed_ip(
            action="create", peer_id=2, address="10.0.0.0/24",
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request, require_create=True)
        _, _, data = capture_call(mock_make_request)
        assert data["address"] == "10.0.0.0"
        assert data["mask"] == 24

    async def test_create_accepts_explicit_mask(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await manage_wireguard_peer_allowed_ip(
            action="create", peer_id=2, address="192.168.5.0", mask=25,
        )
        assert_payload_valid(mock_make_request, require_create=True)
        _, _, data = capture_call(mock_make_request)
        assert data["address"] == "192.168.5.0"
        assert data["mask"] == 25

    async def test_create_bare_address_defaults_to_host_route(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await manage_wireguard_peer_allowed_ip(action="create", peer_id=2, address="10.0.0.7")
        _, _, data = capture_call(mock_make_request)
        assert (data["address"], data["mask"]) == ("10.0.0.7", 32)

    async def test_create_bare_ipv6_defaults_to_128(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await manage_wireguard_peer_allowed_ip(action="create", peer_id=2, address="fd00::1")
        _, _, data = capture_call(mock_make_request)
        assert (data["address"], data["mask"]) == ("fd00::1", 128)

    async def test_create_ipv6_cidr(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await manage_wireguard_peer_allowed_ip(action="create", peer_id=2, address="fd00::/64")
        _, _, data = capture_call(mock_make_request)
        assert (data["address"], data["mask"]) == ("fd00::", 64)

    async def test_conflicting_cidr_and_mask_is_rejected(self, mock_client, mock_make_request):
        result = await manage_wireguard_peer_allowed_ip(
            action="create", peer_id=2, address="10.0.0.0/24", mask=16,
        )
        assert result["success"] is False
        assert "Conflicting prefix" in result["error"]
        assert not mock_make_request.called

    async def test_out_of_range_mask_is_rejected(self, mock_client, mock_make_request):
        result = await manage_wireguard_peer_allowed_ip(
            action="create", peer_id=2, address="10.0.0.0", mask=64,
        )
        assert result["success"] is False
        assert "Invalid mask" in result["error"]
        assert not mock_make_request.called

    async def test_invalid_address_is_rejected(self, mock_client, mock_make_request):
        result = await manage_wireguard_peer_allowed_ip(
            action="create", peer_id=2, address="not-an-ip/24",
        )
        assert result["success"] is False
        assert "Invalid address" in result["error"]
        assert not mock_make_request.called
