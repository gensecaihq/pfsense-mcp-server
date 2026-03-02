"""Backward-compatible re-exports.

Existing code that does ``from src.pfsense_api_enhanced import X`` keeps working.
"""

from .client import EnhancedPfSenseAPIClient
from .helpers import (
    create_date_range_filters,
    create_default_sort,
    create_interface_filter,
    create_ip_filter,
    create_pagination,
    create_port_filter,
)
from .models import (
    AuthMethod,
    ControlParameters,
    PaginationOptions,
    PfSenseVersion,
    QueryFilter,
    SortOptions,
)

__all__ = [
    "EnhancedPfSenseAPIClient",
    "AuthMethod",
    "ControlParameters",
    "PaginationOptions",
    "PfSenseVersion",
    "QueryFilter",
    "SortOptions",
    "create_date_range_filters",
    "create_default_sort",
    "create_interface_filter",
    "create_ip_filter",
    "create_pagination",
    "create_port_filter",
]
