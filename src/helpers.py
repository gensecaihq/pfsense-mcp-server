"""Standalone helper functions for common query patterns and safety guards."""

import ipaddress
import re
from typing import List, Optional, Union

from .models import PaginationOptions, QueryFilter, SortOptions


# Safety constants
MAX_LOG_LINES = 50

# Allowlist of valid pfSense REST API v2 log endpoints
# Maps to /api/v2/status/logs/<type>
VALID_LOG_TYPES = frozenset({
    "firewall", "system", "dhcp", "openvpn", "auth",
})


def create_ip_filter(ip_address: str, operator: str = "exact") -> QueryFilter:
    """Create filter for IP address fields"""
    return QueryFilter("ip", ip_address, operator)


def create_port_filter(port: Union[int, str], field: str = "destination_port", operator: str = "exact") -> QueryFilter:
    """Create filter for port fields"""
    return QueryFilter(field, str(port), operator)


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


def create_pagination(page: int, page_size: int = 50) -> tuple:
    """Create pagination options (capped to avoid pfSense PHP memory exhaustion).

    Returns:
        (PaginationOptions, normalized_page, normalized_page_size)
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 50
    safe_size = min(page_size, MAX_PAGE_SIZE)
    offset = (page - 1) * safe_size
    return PaginationOptions(limit=safe_size, offset=offset), page, safe_size


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


def safe_log_lines(lines: int) -> int:
    """Cap log lines to prevent pfSense PHP memory exhaustion."""
    return max(1, min(lines, MAX_LOG_LINES))


def validate_log_type(log_type: str) -> str:
    """Validate log type against allowlist to prevent path traversal."""
    log_type = log_type.lower().strip()
    if log_type not in VALID_LOG_TYPES:
        raise ValueError(
            f"Invalid log type '{log_type}'. "
            f"Allowed: {', '.join(sorted(VALID_LOG_TYPES))}"
        )
    return log_type


def validate_ip_address(ip: str) -> str:
    """Validate an IP address or network. Returns normalized string."""
    ip = ip.strip()
    if ip.lower() == "any":
        return "any"
    try:
        ipaddress.ip_network(ip, strict=False)
    except ValueError as e:
        raise ValueError(f"Invalid IP address or network '{ip}': {e}") from e
    return ip


def ensure_interface_list(interface: Union[str, list]) -> list:
    """Ensure interface value is a list as required by pfSense API v2."""
    if isinstance(interface, str):
        return [interface]
    return interface


def normalize_protocol(protocol: Optional[str]) -> Optional[str]:
    """Normalize protocol value: 'any' becomes None per pfSense API v2."""
    if protocol is None:
        return None
    if protocol.lower() == "any":
        return None
    return protocol.lower()
