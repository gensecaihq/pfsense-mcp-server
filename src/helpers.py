"""Standalone helper functions for common query patterns."""

from typing import List, Optional, Union

from .models import PaginationOptions, QueryFilter, SortOptions


def create_ip_filter(ip_address: str, operator: str = "exact") -> QueryFilter:
    """Create filter for IP address fields"""
    return QueryFilter("ip", ip_address, operator)


def create_port_filter(port: Union[int, str], operator: str = "exact") -> QueryFilter:
    """Create filter for port fields"""
    return QueryFilter("port", str(port), operator)


def create_interface_filter(interface: str) -> QueryFilter:
    """Create filter for interface fields (uses contains since interface is an array)"""
    return QueryFilter("interface", interface, "contains")


def create_date_range_filters(
    field: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> List[QueryFilter]:
    """Create date range filters"""
    filters = []
    if start_date:
        filters.append(QueryFilter(field, start_date, "gte"))
    if end_date:
        filters.append(QueryFilter(field, end_date, "lte"))
    return filters


def create_pagination(page: int, page_size: int = 50) -> PaginationOptions:
    """Create pagination options"""
    offset = (page - 1) * page_size
    return PaginationOptions(limit=page_size, offset=offset)


def create_default_sort(field: str, descending: bool = False) -> SortOptions:
    """Create default sort options"""
    return SortOptions(
        sort_by=field,
        sort_order="SORT_DESC" if descending else "SORT_ASC"
    )
