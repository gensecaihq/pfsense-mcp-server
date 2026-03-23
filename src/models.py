"""Enums and dataclasses shared across the pfSense MCP server."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class PfSenseVersion(str, Enum):
    CE_2_8_0 = "2.8.0"
    CE_2_8_1 = "2.8.1"
    CE_26_03 = "26.03"      # Requires REST API package build for 26.03 when available
    PLUS_24_11 = "24.11"
    PLUS_25_11 = "25.11"



class AuthMethod(str, Enum):
    BASIC = "basic"
    API_KEY = "api_key"
    JWT = "jwt"


@dataclass
class QueryFilter:
    """Represents a query filter for API requests"""
    field: str
    value: Any
    operator: str = "exact"

    VALID_OPERATORS = frozenset({
        "exact", "startswith", "endswith", "contains",
        "lt", "lte", "gt", "gte", "regex",
    })

    def __post_init__(self):
        if self.operator not in self.VALID_OPERATORS:
            raise ValueError(
                f"Invalid filter operator '{self.operator}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_OPERATORS))}"
            )

    def to_param(self) -> Tuple[str, str]:
        """Convert filter to a (key, value) tuple for URL parameters."""
        if self.operator == "exact":
            return (self.field, str(self.value))
        else:
            return (f"{self.field}__{self.operator}", str(self.value))


@dataclass
class SortOptions:
    """Represents sorting options for API requests"""
    sort_by: Optional[str] = None
    sort_order: str = "SORT_ASC"  # SORT_ASC, SORT_DESC (per pfSense API v2 docs)

    def to_params(self) -> Dict[str, str]:
        """Convert to URL parameters"""
        params = {}
        if self.sort_by:
            params["sort_by"] = self.sort_by
            params["sort_order"] = self.sort_order
        return params


@dataclass
class PaginationOptions:
    """Represents pagination options"""
    limit: Optional[int] = None
    offset: Optional[int] = None

    def to_params(self) -> Dict[str, str]:
        """Convert to URL parameters"""
        params = {}
        if self.limit is not None:
            params["limit"] = str(self.limit)
        if self.offset is not None:
            params["offset"] = str(self.offset)
        return params


@dataclass
class ControlParameters:
    """Represents common control parameters"""
    apply: bool = False
    async_mode: bool = True
    placement: Optional[int] = None
    append: bool = False
    remove: bool = False

    def to_params(self) -> Dict[str, str]:
        """Convert to URL parameters"""
        params = {}
        if self.apply:
            params["apply"] = "true"
        if not self.async_mode:
            params["async"] = "false"
        if self.placement is not None:
            params["placement"] = str(self.placement)
        if self.append:
            params["append"] = "true"
        if self.remove:
            params["remove"] = "true"
        return params
