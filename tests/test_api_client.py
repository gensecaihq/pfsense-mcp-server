"""Unit tests for the API client layer (src/pfsense_api_enhanced.py).

Covers dataclass serialisation, helper functions, Content-Type logic,
query-param assembly, and field remapping in higher-level methods.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.pfsense_api_enhanced import (
    AuthMethod,
    ControlParameters,
    EnhancedPfSenseAPIClient,
    PaginationOptions,
    QueryFilter,
    SortOptions,
    create_default_sort,
    create_interface_filter,
    create_pagination,
)

# ---------------------------------------------------------------------------
# Dataclass serialisation
# ---------------------------------------------------------------------------

class TestQueryFilter:
    def test_exact(self):
        assert QueryFilter("name", "foo").to_param() == "name=foo"

    def test_contains(self):
        assert QueryFilter("name", "foo", "contains").to_param() == "name__contains=foo"

    def test_gte(self):
        assert QueryFilter("age", "18", "gte").to_param() == "age__gte=18"


class TestSortOptions:
    def test_to_params(self):
        s = SortOptions(sort_by="name", sort_order="SORT_ASC")
        assert s.to_params() == {"sort_by": "name", "sort_order": "SORT_ASC"}

    def test_reverse(self):
        s = SortOptions(sort_by="name", reverse=True)
        params = s.to_params()
        assert params["reverse"] == "true"

    def test_empty(self):
        s = SortOptions()
        assert s.to_params() == {}


class TestPaginationOptions:
    def test_to_params(self):
        p = PaginationOptions(limit=10, offset=20)
        assert p.to_params() == {"limit": "10", "offset": "20"}

    def test_empty(self):
        p = PaginationOptions()
        assert p.to_params() == {}


class TestControlParameters:
    def test_apply(self):
        c = ControlParameters(apply=True)
        assert c.to_params()["apply"] == "true"

    def test_placement(self):
        c = ControlParameters(placement=3)
        assert c.to_params()["placement"] == "3"

    def test_append_remove(self):
        c = ControlParameters(append=True, remove=True)
        p = c.to_params()
        assert p["append"] == "true"
        assert p["remove"] == "true"

    def test_async_false(self):
        c = ControlParameters(async_mode=False)
        assert c.to_params()["async"] == "false"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_create_pagination(self):
        p = create_pagination(page=3, page_size=25)
        assert p.limit == 25
        assert p.offset == 50  # (3-1)*25

    def test_create_default_sort_asc(self):
        s = create_default_sort("name")
        assert s.sort_by == "name"
        assert s.sort_order == "SORT_ASC"

    def test_create_default_sort_desc(self):
        s = create_default_sort("name", descending=True)
        assert s.sort_order == "SORT_DESC"

    def test_create_interface_filter(self):
        f = create_interface_filter("wan")
        assert f.field == "interface"
        assert f.value == "wan"
        assert f.operator == "contains"


# ---------------------------------------------------------------------------
# _make_request Content-Type logic
# ---------------------------------------------------------------------------

class TestMakeRequestContentType:
    """Verify that Content-Type is included/excluded correctly."""

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        self.client = EnhancedPfSenseAPIClient(
            host="https://192.0.2.1",
            auth_method=AuthMethod.API_KEY,
            api_key="test-key",
            verify_ssl=False,
        )

    def _mock_response(self, status=200, body=None):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status
        resp.json.return_value = body or {"data": []}
        resp.text = json.dumps(body or {"data": []})
        return resp

    async def test_get_omits_content_type(self):
        resp = self._mock_response()
        with patch.object(self.client, "_ensure_client"):
            self.client.client = MagicMock()
            self.client.client.get = AsyncMock(return_value=resp)
            await self.client._make_request("GET", "/firewall/rules")
            headers = self.client.client.get.call_args.kwargs["headers"]
            assert "Content-Type" not in headers

    async def test_post_includes_content_type(self):
        resp = self._mock_response()
        with patch.object(self.client, "_ensure_client"):
            self.client.client = MagicMock()
            self.client.client.post = AsyncMock(return_value=resp)
            await self.client._make_request("POST", "/firewall/rule", data={"type": "pass"})
            headers = self.client.client.post.call_args.kwargs["headers"]
            assert headers["Content-Type"] == "application/json"

    async def test_delete_with_body_includes_content_type(self):
        resp = self._mock_response()
        with patch.object(self.client, "_ensure_client"):
            self.client.client = MagicMock()
            self.client.client.delete = AsyncMock(return_value=resp)
            await self.client._make_request("DELETE", "/firewall/rule", data={"id": 0})
            headers = self.client.client.delete.call_args.kwargs["headers"]
            assert headers["Content-Type"] == "application/json"

    async def test_delete_without_body_omits_content_type(self):
        resp = self._mock_response()
        with patch.object(self.client, "_ensure_client"):
            self.client.client = MagicMock()
            self.client.client.delete = AsyncMock(return_value=resp)
            await self.client._make_request("DELETE", "/firewall/rule")
            headers = self.client.client.delete.call_args.kwargs["headers"]
            assert "Content-Type" not in headers


# ---------------------------------------------------------------------------
# _make_request error handling
# ---------------------------------------------------------------------------

class TestMakeRequestErrors:
    async def test_4xx_raises(self):
        client = EnhancedPfSenseAPIClient(
            host="https://192.0.2.1",
            auth_method=AuthMethod.API_KEY,
            api_key="test-key",
            verify_ssl=False,
        )
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = 404
        resp.text = '{"message":"not found"}'
        resp.json.return_value = {"message": "not found"}

        with patch.object(client, "_ensure_client"):
            client.client = MagicMock()
            client.client.get = AsyncMock(return_value=resp)
            with pytest.raises(Exception, match="404"):
                await client._make_request("GET", "/nope")


# ---------------------------------------------------------------------------
# _build_query_params
# ---------------------------------------------------------------------------

class TestBuildQueryParams:
    def test_assembly(self):
        client = EnhancedPfSenseAPIClient(
            host="https://192.0.2.1",
            auth_method=AuthMethod.API_KEY,
            api_key="k",
            verify_ssl=False,
        )
        qs = client._build_query_params(
            filters=[QueryFilter("name", "test", "contains")],
            sort=SortOptions(sort_by="name"),
            pagination=PaginationOptions(limit=10, offset=0),
        )
        assert "name__contains=test" in qs
        assert "sort_by=name" in qs
        assert "limit=10" in qs


# ---------------------------------------------------------------------------
# Higher-level method field remapping
# ---------------------------------------------------------------------------

class TestGetFirewallRulesRemap:
    """get_firewall_rules must rewrite sort_by='sequence' to 'tracker'."""

    async def test_sequence_to_tracker(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await mock_client.get_firewall_rules(
            sort=SortOptions(sort_by="sequence"),
        )
        call_kwargs = mock_make_request.call_args
        sort = call_kwargs.kwargs.get("sort") or call_kwargs[1].get("sort")
        assert sort.sort_by == "tracker"


class TestGetDhcpLeasesIfFilter:
    """get_dhcp_leases must map interface to the 'if' field."""

    async def test_interface_becomes_if(self, mock_client, mock_make_request):
        mock_make_request.return_value = {"data": []}
        await mock_client.get_dhcp_leases(interface="lan")
        call_kwargs = mock_make_request.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert any(f.field == "if" for f in filters)
