"""Unit tests for system_advanced tools (src/tools/system_advanced.py).

Focus on the pfSense REST API wire-format contract: these tools must forward
the exact field names the API expects, otherwise values are silently dropped
(see issues #7 and #13).
"""

from src.tools.system_advanced import update_log_settings, update_webgui_settings

_update_log_settings = update_log_settings.fn
_update_webgui_settings = update_webgui_settings.fn


def _sent_data(mock_make_request):
    """Extract the JSON body passed to _make_request."""
    call = mock_make_request.call_args
    return call.kwargs.get("data") or call.args[2]


# ---------------------------------------------------------------------------
# update_log_settings — wire-format field names (issue #13, PR #11)
# ---------------------------------------------------------------------------

class TestUpdateLogSettings:
    async def test_remote_syslog_uses_api_field_names(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _update_log_settings(
            enableremotelogging=True,
            remoteserver="172.16.0.100:1514",
            ipprotocol="ipv4",
            reverseorder=True,
            format="rfc5424",
        )
        assert result["success"] is True
        data = _sent_data(mock_make_request)
        # Correct pfSense API field names must be present...
        assert data["enableremotelogging"] is True
        assert data["ipprotocol"] == "ipv4"
        assert data["reverseorder"] is True
        assert data["remoteserver"] == "172.16.0.100:1514"
        # ...and the old (broken) names must NOT be sent.
        assert "ipproto" not in data
        assert "reverse" not in data

    async def test_per_category_toggles(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await _update_log_settings(vpn=True, system=True, auth=False, resolver=True)
        data = _sent_data(mock_make_request)
        assert data["vpn"] is True
        assert data["system"] is True
        assert data["auth"] is False
        assert data["resolver"] is True

    async def test_logconfigchanges(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await _update_log_settings(logconfigchanges=True)
        assert _sent_data(mock_make_request)["logconfigchanges"] is True

    async def test_unset_fields_omitted(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        await _update_log_settings(format="rfc5424")
        data = _sent_data(mock_make_request)
        assert data == {"format": "rfc5424"}

    async def test_no_fields_is_error(self, mock_client, mock_make_request):
        result = await _update_log_settings()
        assert result["success"] is False
        assert "No fields to update" in result["error"]
        mock_make_request.assert_not_called()


# ---------------------------------------------------------------------------
# update_webgui_settings — port must be sent as a string (issue #7)
# ---------------------------------------------------------------------------

class TestUpdateWebguiSettings:
    async def test_port_sent_as_string(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _update_webgui_settings(port=10443)
        assert result["success"] is True
        data = _sent_data(mock_make_request)
        assert data["port"] == "10443"
        assert isinstance(data["port"], str)

    async def test_port_out_of_range_rejected(self, mock_client, mock_make_request):
        result = await _update_webgui_settings(port=70000)
        assert result["success"] is False
        assert "between 1 and 65535" in result["error"]
        mock_make_request.assert_not_called()

    async def test_invalid_protocol_rejected(self, mock_client, mock_make_request):
        result = await _update_webgui_settings(protocol="ftp")
        assert result["success"] is False
        mock_make_request.assert_not_called()
