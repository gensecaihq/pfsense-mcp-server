"""Unit tests for DNS Resolver settings tools."""

from src.tools.dns_resolver import update_dns_resolver_settings

_update_dns_resolver_settings = update_dns_resolver_settings.fn


def _sent_data(mock_make_request):
    call = mock_make_request.call_args
    return call.kwargs.get("data") or call.args[2]


class TestUpdateDnsResolverSettings:
    async def test_active_interfaces_use_api_field_name(
        self, mock_client, mock_make_request
    ):
        mock_make_request.return_value = {"data": {}}

        result = await _update_dns_resolver_settings(
            active_interfaces=["lan", "opt7"],
        )

        assert result["success"] is True
        assert _sent_data(mock_make_request) == {
            "active_interface": ["lan", "opt7"],
        }

    async def test_unset_active_interfaces_are_omitted(
        self, mock_client, mock_make_request
    ):
        mock_make_request.return_value = {"data": {}}

        await _update_dns_resolver_settings(forwarding=True)

        assert _sent_data(mock_make_request) == {"forwarding": True}
