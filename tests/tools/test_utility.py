"""Unit tests for utility tools (src/tools/utility.py)."""

import pytest

from src.tools.utility import (
    _validate_endpoint,
    disable_hateoas,
    enable_hateoas,
    find_object_by_field,
    follow_api_link,
    get_api_capabilities,
    refresh_object_ids,
    test_enhanced_connection,
)

_follow_api_link = follow_api_link
_enable_hateoas = enable_hateoas
_disable_hateoas = disable_hateoas
_refresh_object_ids = refresh_object_ids
_find_object_by_field = find_object_by_field
_get_api_capabilities = get_api_capabilities
_test_enhanced_connection = test_enhanced_connection


# ---------------------------------------------------------------------------
# follow_api_link
# ---------------------------------------------------------------------------

class TestFollowApiLink:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("link failed")
        result = await _follow_api_link(link_url="/firewall/rules")
        assert result["success"] is False
        assert "link failed" in result["error"]

    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": [{"id": 1}], "_links": {}}
        result = await _follow_api_link(link_url="/firewall/rules")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# enable/disable HATEOAS
# ---------------------------------------------------------------------------

class TestEnableDisableHateoas:
    async def test_enable(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"hateoas": True}}
        result = await _enable_hateoas(confirm=True)
        assert result["success"] is True
        # Verify it calls PATCH on the API
        mock_make_request.assert_called_once()

    async def test_disable(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"hateoas": False}}
        result = await _disable_hateoas(confirm=True)
        assert result["success"] is True
        mock_make_request.assert_called_once()

    async def test_enable_requires_confirm(self, mock_client, mock_make_request):
        result = await _enable_hateoas()
        assert result["success"] is False
        assert "confirm" in result["error"].lower()

    async def test_disable_requires_confirm(self, mock_client, mock_make_request):
        result = await _disable_hateoas()
        assert result["success"] is False
        assert "confirm" in result["error"].lower()


# ---------------------------------------------------------------------------
# refresh_object_ids
# ---------------------------------------------------------------------------

class TestRefreshObjectIds:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("refresh failed")
        result = await _refresh_object_ids(endpoint="/firewall/rules")
        assert result["success"] is False
        assert "refresh failed" in result["error"]

    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": [{"id": 0}, {"id": 1}]}
        result = await _refresh_object_ids(endpoint="/firewall/rules")
        assert result["success"] is True
        assert result["refreshed_count"] == 2


# ---------------------------------------------------------------------------
# find_object_by_field
# ---------------------------------------------------------------------------

class TestFindObjectByField:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("find failed")
        result = await _find_object_by_field(
            endpoint="/firewall/aliases", field="name", value="x"
        )
        assert result["success"] is False
        assert "find failed" in result["error"]

    async def test_found(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": [{"id": 3, "name": "blocked_hosts"}]}
        result = await _find_object_by_field(
            endpoint="/firewall/aliases", field="name", value="blocked_hosts"
        )
        assert result["success"] is True
        assert result["found"] is True
        assert result["object_id"] == 3

    async def test_not_found(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        result = await _find_object_by_field(
            endpoint="/firewall/aliases", field="name", value="nonexistent"
        )
        assert result["success"] is True
        assert result["found"] is False

    async def test_resolves_an_interface_by_descr(
        self, mock_client, mock_make_request, interfaces_response
    ):
        """The collection path is /interfaces, and it must reach the endpoint.

        Interfaces are keyed by name rather than by array index, so looking one
        up by descr is the supported way to get the id that update_interface
        and delete_interface take.
        """
        mock_make_request.return_value = {
            "data": [i for i in interfaces_response["data"] if i["descr"] == "MGMT"]
        }
        result = await _find_object_by_field(
            endpoint="/interfaces", field="descr", value="MGMT"
        )
        assert result["success"] is True
        assert result["found"] is True
        assert result["object_id"] == "opt16"

    async def test_rejects_endpoint_outside_the_allowlist(
        self, mock_client, mock_make_request
    ):
        result = await _find_object_by_field(
            endpoint="/secrets", field="descr", value="x"
        )
        assert result["success"] is False
        assert "not in the allowed list" in result["error"]
        mock_make_request.assert_not_called()


# ---------------------------------------------------------------------------
# _validate_endpoint
# ---------------------------------------------------------------------------

class TestValidateEndpoint:
    def test_accepts_model_and_collection_spellings(self):
        for endpoint in (
            "/interface",
            "/interfaces",
            "/interface/vlan",
            "/firewall/rules",
            "/status/logs/firewall",
            "/users",
            "/certificates",
        ):
            assert _validate_endpoint(endpoint) == endpoint

    def test_adds_a_leading_slash(self):
        assert _validate_endpoint("interfaces") == "/interfaces"

    def test_rejects_traversal(self):
        with pytest.raises(ValueError, match=r"\.\."):
            _validate_endpoint("/system/../../etc/passwd")

    def test_rejects_a_segment_that_merely_starts_with_an_allowed_root(self):
        """Matching is on the whole first segment, not a bare string prefix."""
        for endpoint in ("/systemfoo", "/interfacex", "/vpnadmin"):
            with pytest.raises(ValueError, match="not in the allowed list"):
                _validate_endpoint(endpoint)

    def test_rejects_an_unknown_root(self):
        with pytest.raises(ValueError, match="not in the allowed list"):
            _validate_endpoint("/secrets/dump")


# ---------------------------------------------------------------------------
# get_api_capabilities
# ---------------------------------------------------------------------------

class TestGetApiCapabilities:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("caps failed")
        result = await _get_api_capabilities()
        assert result["success"] is False
        assert "caps failed" in result["error"]

    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"version": "2.0"}}
        result = await _get_api_capabilities()
        assert result["success"] is True
        assert result["api_version"] == "v2"


# ---------------------------------------------------------------------------
# test_enhanced_connection
# ---------------------------------------------------------------------------

class TestTestEnhancedConnection:
    async def test_connected(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"status": "ok"}}
        result = await _test_enhanced_connection()
        assert result["success"] is True
        assert result["basic_connection"] is True

    async def test_features_failed(self, mock_client, mock_make_request):
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"data": {"status": "ok"}}  # system status ok
            raise Exception("feature not supported")

        mock_make_request.side_effect = side_effect
        result = await _test_enhanced_connection()
        assert result["success"] is True
        failed = [t for t in result["feature_tests"] if t["status"] == "failed"]
        assert len(failed) > 0

    async def test_not_connected(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("connection refused")
        result = await _test_enhanced_connection()
        assert result["success"] is False
