"""Unit tests for alias tools (src/tools/aliases.py)."""

from src.tools.aliases import (
    create_alias,
    delete_alias,
    manage_alias_addresses,
    search_aliases,
    update_alias,
)

_search_aliases = search_aliases.fn
_create_alias = create_alias.fn
_manage_alias_addresses = manage_alias_addresses.fn
_update_alias = update_alias.fn
_delete_alias = delete_alias.fn


# ---------------------------------------------------------------------------
# search_aliases
# ---------------------------------------------------------------------------

class TestSearchAliases:
    async def test_search_by_name(self, mock_client, mock_make_request, aliases_response):
        mock_make_request.return_value = aliases_response
        result = await _search_aliases(search_term="blocked")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "name" and f.value == "blocked" for f in filters)

    async def test_filter_by_type(self, mock_client, mock_make_request, aliases_response):
        mock_make_request.return_value = aliases_response
        result = await _search_aliases(alias_type="host")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "type" and f.value == "host" for f in filters)

    async def test_containing_ip_filter(self, mock_client, mock_make_request, aliases_response):
        mock_make_request.return_value = aliases_response
        result = await _search_aliases(containing_ip="10.0.0.1")
        assert result["success"] is True
        filters = mock_make_request.call_args.kwargs.get("filters") or mock_make_request.call_args[1].get("filters")
        assert any(f.field == "address" and f.value == "10.0.0.1" and f.operator == "contains" for f in filters)

    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("server error")
        result = await _search_aliases()
        assert result["success"] is False
        assert "server error" in result["error"]


# ---------------------------------------------------------------------------
# create_alias
# ---------------------------------------------------------------------------

class TestCreateAlias:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("create failed")
        result = await _create_alias(
            name="a", alias_type="host", addresses=["10.0.0.1"],
        )
        assert result["success"] is False
        assert "create failed" in result["error"]

    async def test_correct_data(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 2, "name": "test_alias"}}
        result = await _create_alias(
            name="test_alias", alias_type="host",
            addresses=["10.0.0.1"], description="Test",
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["name"] == "test_alias"
        assert data["type"] == "host"
        assert data["address"] == ["10.0.0.1"]
        assert data["descr"] == "Test"

    async def test_details_parameter(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 3, "name": "test_alias"}}
        result = await _create_alias(
            name="test_alias", alias_type="host",
            addresses=["10.0.0.1"], details=["entry desc"],
        )
        assert result["success"] is True
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["detail"] == ["entry desc"]

    async def test_apply_immediately_false(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 4, "name": "deferred"}}
        result = await _create_alias(
            name="deferred", alias_type="host",
            addresses=["10.0.0.1"], apply_immediately=False,
        )
        assert result["success"] is True
        assert result["applied"] is False


# ---------------------------------------------------------------------------
# manage_alias_addresses
# ---------------------------------------------------------------------------

class TestManageAliasAddresses:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("alias update failed")
        result = await _manage_alias_addresses(
            alias_id=0, action="add", addresses=["10.0.0.3"],
        )
        assert result["success"] is False
        assert "alias update failed" in result["error"]

    async def test_add(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _manage_alias_addresses(
            alias_id=0, action="add", addresses=["10.0.0.3"],
        )
        assert result["success"] is True
        assert result["action"] == "add"

    async def test_remove(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0}}
        result = await _manage_alias_addresses(
            alias_id=0, action="remove", addresses=["10.0.0.1"],
        )
        assert result["success"] is True
        assert result["action"] == "remove"

    async def test_invalid_action(self, mock_client, mock_make_request):
        result = await _manage_alias_addresses(
            alias_id=0, action="purge", addresses=["10.0.0.1"],
        )
        assert result["success"] is False
        assert "add" in result["error"] and "remove" in result["error"]


# ---------------------------------------------------------------------------
# update_alias
# ---------------------------------------------------------------------------

class TestUpdateAlias:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("patch failed")
        result = await _update_alias(alias_id=0, name="x")
        assert result["success"] is False
        assert "patch failed" in result["error"]

    async def test_basic_update(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 0, "name": "updated"}}
        result = await _update_alias(alias_id=0, name="updated", description="new desc")
        assert result["success"] is True
        assert result["alias_id"] == 0
        assert "name" in result["fields_updated"]
        assert "descr" in result["fields_updated"]

    async def test_partial_fields(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"id": 1}}
        result = await _update_alias(alias_id=1, addresses=["10.0.0.5"])
        assert result["success"] is True
        assert "address" in result["fields_updated"]

    async def test_no_fields_error(self, mock_client, mock_make_request):
        result = await _update_alias(alias_id=0)
        assert result["success"] is False
        assert "No fields" in result["error"]


# ---------------------------------------------------------------------------
# delete_alias
# ---------------------------------------------------------------------------

class TestDeleteAlias:
    async def test_error(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("delete failed")
        result = await _delete_alias(alias_id=0)
        assert result["success"] is False
        assert "delete failed" in result["error"]

    async def test_passes_id_and_applies(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {}}
        result = await _delete_alias(alias_id=2)
        assert result["success"] is True
        assert result["alias_id"] == 2
        data = mock_make_request.call_args.kwargs.get("data") or mock_make_request.call_args[1].get("data")
        assert data["id"] == 2
