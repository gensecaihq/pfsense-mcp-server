"""Unit tests for interface tools (src/tools/interfaces.py)."""

import inspect

from src.tools.interfaces import (
    delete_interface,
    search_interface_configs,
    update_interface,
)

_search_interface_configs = search_interface_configs
_update_interface = update_interface
_delete_interface = delete_interface


def _sent_data(mock_make_request):
    call = mock_make_request.call_args
    return call.kwargs.get("data") or call[1].get("data") or {}


# ---------------------------------------------------------------------------
# Interface IDs are name strings
# ---------------------------------------------------------------------------

class TestInterfaceIdType:
    """The API keys interfaces by config name, so the id is a string.

    Declaring these parameters as int made every interface on a real box
    unaddressable: the call failed Pydantic validation before a request was
    sent, and any integer that did validate would target a different object
    than the operator named.
    """

    def test_update_and_delete_declare_string_ids(self):
        for tool in (update_interface, delete_interface):
            annotation = inspect.signature(tool).parameters["interface_id"].annotation
            assert annotation is str, f"{tool.__name__} must take interface_id as str"

    async def test_recorded_ids_are_non_numeric_strings(
        self, mock_client, mock_make_request, interfaces_response
    ):
        mock_make_request.return_value = interfaces_response
        result = await _search_interface_configs()

        ids = [i["id"] for i in result["interfaces"]]
        assert ids == ["wan", "lan", "opt16", "opt17"]
        for value in ids:
            assert isinstance(value, str)
            assert not value.isdigit()

    async def test_update_sends_the_name_as_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": "opt16"}}
        result = await _update_interface(interface_id="opt16", ipaddr="10.9.254.1", subnet=24)

        assert result["success"] is True
        data = _sent_data(mock_make_request)
        assert data["id"] == "opt16"
        assert data["ipaddr"] == "10.9.254.1"
        assert data["subnet"] == 24

    async def test_delete_sends_the_name_as_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _delete_interface(interface_id="opt17", confirm=True)

        assert result["success"] is True
        assert _sent_data(mock_make_request)["id"] == "opt17"

    async def test_delete_still_requires_confirm(self, mock_client, mock_make_request):
        result = await _delete_interface(interface_id="opt17")
        assert result["success"] is False
        mock_make_request.assert_not_called()


# ---------------------------------------------------------------------------
# search_interface_configs — null-safe client-side filter
# ---------------------------------------------------------------------------

class TestSearchInterfaceConfigs:
    async def test_no_search_term_returns_all(
        self, mock_client, mock_make_request, interfaces_response
    ):
        mock_make_request.return_value = interfaces_response
        result = await _search_interface_configs()
        assert result["success"] is True
        assert result["count"] == 4

    async def test_search_term_with_null_fields(
        self, mock_client, mock_make_request, interfaces_response
    ):
        """Rows carrying null ipaddr must not break the filter."""
        mock_make_request.return_value = interfaces_response
        result = await _search_interface_configs(search_term="MGMT")

        assert result["success"] is True
        assert result["count"] == 1
        assert result["interfaces"][0]["id"] == "opt16"

    async def test_search_matches_ipaddr_and_if(
        self, mock_client, mock_make_request, interfaces_response
    ):
        mock_make_request.return_value = interfaces_response
        by_ip = await _search_interface_configs(search_term="10.9.254")
        assert [i["id"] for i in by_ip["interfaces"]] == ["opt16"]

        by_port = await _search_interface_configs(search_term="ix0.254")
        assert [i["id"] for i in by_port["interfaces"]] == ["opt16"]

    async def test_null_field_does_not_match_none(
        self, mock_client, mock_make_request, interfaces_response
    ):
        """A null ipaddr must not answer to a search for "none"."""
        mock_make_request.return_value = interfaces_response
        result = await _search_interface_configs(search_term="none")

        # Only the typev4="none" row matches, and it matches on no field here
        # because typev4 is not one of the searched fields.
        assert result["count"] == 0
