"""Unit tests for utility tools (src/tools/utility.py)."""

from src.tools.utility import (
    disable_hateoas,
    enable_hateoas,
    find_object_by_field,
    follow_api_link,
    get_api_capabilities,
    refresh_object_ids,
    test_enhanced_connection,
)

_follow_api_link = follow_api_link.fn
_enable_hateoas = enable_hateoas.fn
_disable_hateoas = disable_hateoas.fn
_refresh_object_ids = refresh_object_ids.fn
_find_object_by_field = find_object_by_field.fn
_get_api_capabilities = get_api_capabilities.fn
_test_enhanced_connection = test_enhanced_connection.fn


# ---------------------------------------------------------------------------
# follow_api_link
# ---------------------------------------------------------------------------

class TestFollowApiLink:
    async def test_basic(self, mock_client, mock_make_request):
        # follow_link uses client.client directly, not _make_request
        from unittest.mock import AsyncMock, MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": 1}], "_links": {}}
        mock_response.raise_for_status = MagicMock()
        mock_client.client = MagicMock()
        mock_client.client.get = AsyncMock(return_value=mock_response)
        result = await _follow_api_link(link_url="/firewall/rules")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# enable/disable HATEOAS
# ---------------------------------------------------------------------------

class TestEnableDisableHateoas:
    async def test_enable(self, mock_client, mock_make_request):
        result = await _enable_hateoas()
        assert result["success"] is True
        assert mock_client.hateoas_enabled is True

    async def test_disable(self, mock_client, mock_make_request):
        result = await _disable_hateoas()
        assert result["success"] is True
        assert mock_client.hateoas_enabled is False


# ---------------------------------------------------------------------------
# refresh_object_ids
# ---------------------------------------------------------------------------

class TestRefreshObjectIds:
    async def test_basic(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": [{"id": 0}, {"id": 1}]}
        result = await _refresh_object_ids(endpoint="/firewall/rules")
        assert result["success"] is True
        assert result["refreshed_count"] == 2


# ---------------------------------------------------------------------------
# find_object_by_field
# ---------------------------------------------------------------------------

class TestFindObjectByField:
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


# ---------------------------------------------------------------------------
# get_api_capabilities
# ---------------------------------------------------------------------------

class TestGetApiCapabilities:
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
