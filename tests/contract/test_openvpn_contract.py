"""Contract tests for the OpenVPN family wire fixes.

Before these fixes the whole create/update/CSO/export surface used field names
the upstream models don't have (crypto/ca/cert/descr/disabled/server_id) or
wrong types (int ports, int dh_length), so servers/clients could not be created
and — worse — a dropped `disabled` left a new tunnel LIVE and a dropped CSO
`server_id` applied the override to ALL servers.
"""
from src.tools.vpn_openvpn import (
    create_openvpn_client,
    create_openvpn_server,
    export_openvpn_client_config,
    manage_openvpn_cso,
    update_openvpn_client,
    update_openvpn_server,
)
from tests.contract.schema import assert_payload_valid, capture_call


class TestServer:
    async def test_create_field_names_and_types(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_openvpn_server(
            mode="server_tls", protocol="UDP4", dev_mode="tun", interface="wan",
            local_port=1194, ca="ca1", cert="crt1", crypto="AES-256-GCM",
            dh_length=2048, compression="lzo", description="office",
            custom_options="push route 10.0.0.0 255.0.0.0", disabled=True,
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/vpn/openvpn/server"
        assert data["local_port"] == "1194"          # string port
        assert data["disable"] is True                # not `disabled`
        assert data["description"] == "office"        # not `descr`
        assert data["caref"] == "ca1" and data["certref"] == "crt1"
        assert data["data_ciphers"] == ["AES-256-GCM"]  # array, not `crypto`
        assert data["dh_length"] == "2048"            # string
        assert data["allow_compression"] == "yes"     # mapped from lzo
        assert data["custom_options"] == ["push route 10.0.0.0 255.0.0.0"]
        for stale in ("disabled", "descr", "ca", "cert", "crypto", "compression"):
            assert stale not in data

    async def test_update_field_names(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_openvpn_server(server_id=1, local_port=1195, disabled=False, crypto="AES-128-GCM")
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["local_port"] == "1195" and data["disable"] is False
        assert data["data_ciphers"] == ["AES-128-GCM"]


class TestClient:
    async def test_create_field_names_and_string_ports(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await create_openvpn_client(
            server_addr="vpn.example.com", server_port=1194, protocol="UDP4",
            dev_mode="tun", interface="wan", ca="ca1", cert="crt1",
            proxy_port=8080, disabled=True,
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["server_port"] == "1194" and data["proxy_port"] == "8080"
        assert data["disable"] is True and data["caref"] == "ca1" and data["certref"] == "crt1"

    async def test_update_field_names(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await update_openvpn_client(client_id=2, server_port=1195, crypto="AES-256-GCM")
        assert_payload_valid(mock_make_request)
        _, _, data = capture_call(mock_make_request)
        assert data["server_port"] == "1195" and data["data_ciphers"] == ["AES-256-GCM"]


class TestCso:
    async def test_create_uses_server_list_and_description(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await manage_openvpn_cso(
            action="create", common_name="alice", server_list=["ovpns1"],
            description="alice override", tunnel_network="10.0.8.5/32",
            local_network="192.168.1.0/24", disabled=True,
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/vpn/openvpn/cso"
        assert data["server_list"] == ["ovpns1"]      # not `server_id` (fleet-wide!)
        assert data["description"] == "alice override"
        assert data["disable"] is True
        assert data["local_network"] == ["192.168.1.0/24"]  # array
        for stale in ("server_id", "descr", "disabled", "redirect_gateway"):
            assert stale not in data


class TestExport:
    async def test_uses_valid_field_names(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await export_openvpn_client_config(
            server_id=1, export_type="confinline", use_token=True,
            proxy_addr="proxy", proxy_port=8080, silent_install=True,
        )
        assert result["success"] is True
        assert_payload_valid(mock_make_request)
        _, endpoint, data = capture_call(mock_make_request)
        assert endpoint == "/vpn/openvpn/client_export"
        assert data["server"] == 1 and data["type"] == "confinline"
        assert data["usetoken"] is True and data["proxyport"] == "8080"
        assert data["silent"] is True
        for stale in ("server_id", "export_type", "use_token", "proxy_port", "silent_install"):
            assert stale not in data
