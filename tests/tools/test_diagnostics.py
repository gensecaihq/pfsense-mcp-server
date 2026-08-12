"""Tests for diagnostics tools."""
from src.tools.diagnostics import get_pf_table, search_pf_tables


def _call(mock_make_request):
    """Extract (method, endpoint, extra_params) from the mocked request."""
    args, kwargs = mock_make_request.call_args
    method = kwargs.get("method", args[0] if args else None)
    endpoint = kwargs.get("endpoint", args[1] if len(args) > 1 else None)
    return method, endpoint, kwargs.get("extra_params") or {}


class TestGetPfTable:
    """The Table model is a many-model keyed by table name (`id_type = 'string'`),
    so a single table is read by id on the singular endpoint."""

    async def test_requests_table_by_id(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": {"name": "bogons", "entries": ["10.0.0.0/8", "192.168.0.0/16"]},
        }
        result = await get_pf_table(name="bogons")

        assert result["success"] is True
        method, endpoint, extra_params = _call(mock_make_request)
        assert (method, endpoint) == ("GET", "/diagnostics/table")
        assert extra_params == {"id": "bogons"}

    async def test_returns_entries_and_count(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": {"name": "sshlockout", "entries": ["203.0.113.5", "203.0.113.9"]},
        }
        result = await get_pf_table(name="sshlockout")

        assert result["table_name"] == "sshlockout"
        assert result["count"] == 2
        assert result["entries"] == ["203.0.113.5", "203.0.113.9"]

    async def test_empty_table_reports_zero(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"name": "virusprot", "entries": []}}
        result = await get_pf_table(name="virusprot")

        assert result["success"] is True
        assert result["count"] == 0
        assert result["entries"] == []

    async def test_name_is_trimmed(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": {"name": "bogons", "entries": []}}
        await get_pf_table(name="  bogons  ")

        _, _, extra_params = _call(mock_make_request)
        assert extra_params == {"id": "bogons"}

    async def test_blank_name_is_rejected(self, mock_client, mock_make_request):
        result = await get_pf_table(name="   ")

        assert result["success"] is False
        assert "name is required" in result["error"]
        assert not mock_make_request.called

    async def test_malformed_data_does_not_raise(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": None}
        result = await get_pf_table(name="bogons")

        assert result["success"] is True
        assert result["count"] == 0
        assert result["table_name"] == "bogons"

    async def test_api_error_is_surfaced(self, mock_client, mock_make_request):
        mock_make_request.side_effect = Exception("404 Not Found")
        result = await get_pf_table(name="nosuchtable")

        assert result["success"] is False
        assert "404 Not Found" in result["error"]


class TestSearchPfTables:
    async def test_lists_all_tables(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [{"name": "bogons", "entries": []}, {"name": "sshlockout", "entries": []}],
        }
        result = await search_pf_tables()

        assert result["success"] is True
        assert result["count"] == 2
        _, endpoint, _ = _call(mock_make_request)
        assert endpoint == "/diagnostics/tables"

    async def test_search_term_filters_by_name(self, mock_client, mock_make_request):
        mock_make_request.return_value = {
            "data": [{"name": "bogons", "entries": []}, {"name": "sshlockout", "entries": []}],
        }
        result = await search_pf_tables(search_term="ssh")

        assert result["count"] == 1
        assert result["pf_tables"][0]["name"] == "sshlockout"
