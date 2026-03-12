"""Standalone helper functions for common query patterns."""

import re
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


MAX_PAGE_SIZE = 200


def create_pagination(page: int, page_size: int = 50) -> PaginationOptions:
    """Create pagination options (capped to avoid pfSense PHP memory exhaustion)"""
    if page < 1:
        page = 1
    safe_size = min(page_size, MAX_PAGE_SIZE)
    offset = (page - 1) * safe_size
    return PaginationOptions(limit=safe_size, offset=offset)


def create_default_sort(field: str, descending: bool = False) -> SortOptions:
    """Create default sort options"""
    return SortOptions(
        sort_by=field,
        sort_order="SORT_DESC" if descending else "SORT_ASC"
    )


# Valid port value: single port (443), range (1024-65535), or alias name (alphanumeric/underscore)
_PORT_RE = re.compile(r"^(\d{1,5}(-\d{1,5})?|[A-Za-z_]\w*)$")

_MAX_PORT = 65535


def validate_port_value(value: str, field_name: str = "port") -> Optional[str]:
    """Return an error message if the port value looks invalid, else None."""
    stripped = value.strip() if value else ""
    if not stripped:
        return None

    m = _PORT_RE.match(stripped)
    if not m:
        return (
            f"Invalid {field_name} '{value}'. "
            "Use a single port (443), a range (1024-65535), or an alias name. "
            "Multiple ports require a port alias — create one first with create_alias."
        )

    # If it matched the numeric pattern, validate port bounds and range ordering
    if stripped[0].isdigit():
        parts = stripped.split("-")
        for p in parts:
            if int(p) < 1 or int(p) > _MAX_PORT:
                return (
                    f"Invalid {field_name} '{value}': port numbers must be 1-{_MAX_PORT}."
                )
        if len(parts) == 2 and int(parts[0]) > int(parts[1]):
            return (
                f"Invalid {field_name} '{value}': range start must be <= range end."
            )

    return None
