"""Tests for the search-pagination fix.

Search tools filter ``search_term`` client-side. Previously they did so *after*
server-side pagination, silently hiding matches beyond the first page. They now
fetch the full window (up to the MAX_PAGE_SIZE cap) whenever a search term is
active, so the client-side filter sees every object.
"""
from src.helpers import MAX_PAGE_SIZE, create_pagination, create_search_pagination


class TestCreateSearchPagination:
    def test_no_search_term_matches_normal_pagination(self):
        assert create_search_pagination(2, 20, None)[0].limit == create_pagination(2, 20)[0].limit
        opts, page, size = create_search_pagination(2, 20, None)
        assert opts.offset == create_pagination(2, 20)[0].offset

    def test_search_term_fetches_full_window(self):
        opts, page, size = create_search_pagination(3, 20, "web")
        assert opts.limit == MAX_PAGE_SIZE
        assert opts.offset == 0  # start from the top so nothing is skipped
        assert size == MAX_PAGE_SIZE

    def test_empty_search_term_is_treated_as_no_search(self):
        assert create_search_pagination(1, 20, "")[0].limit == create_pagination(1, 20)[0].limit


class TestSearchToolUsesFullWindow:
    async def test_search_dhcp_leases_widens_fetch_when_searching(
        self, mock_client, mock_make_request, dhcp_leases_response
    ):
        from src.tools.dhcp import search_dhcp_leases

        mock_make_request.return_value = dhcp_leases_response
        await search_dhcp_leases(search_term="laptop", page_size=20)
        pagination = mock_make_request.call_args.kwargs.get("pagination")
        assert pagination is not None and pagination.limit == MAX_PAGE_SIZE

    async def test_search_dhcp_leases_normal_page_without_search(
        self, mock_client, mock_make_request, dhcp_leases_response
    ):
        from src.tools.dhcp import search_dhcp_leases

        mock_make_request.return_value = dhcp_leases_response
        await search_dhcp_leases(page_size=20)
        pagination = mock_make_request.call_args.kwargs.get("pagination")
        assert pagination is not None and pagination.limit == 20
