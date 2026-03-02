"""Enums and dataclasses shared across the pfSense MCP server."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PfSenseVersion(str, Enum):
    CE_2_8_0 = "2.8.0"
    PLUS_24_11 = "24.11"


class AuthMethod(str, Enum):
    BASIC = "basic"
    API_KEY = "api_key"
    JWT = "jwt"


@dataclass
class QueryFilter:
    """Represents a query filter for API requests"""
    field: str
    value: Any
    operator: str = "exact"  # exact, startswith, endswith, contains, lt, lte, gt, gte, regex

    def to_param(self) -> str:
        """Convert filter to URL parameter"""
        if self.operator == "exact":
            return f"{self.field}={self.value}"
        else:
            return f"{self.field}__{self.operator}={self.value}"


@dataclass
class SortOptions:
    """Represents sorting options for API requests"""
    sort_by: Optional[str] = None
    sort_order: str = "SORT_ASC"  # SORT_ASC, SORT_DESC (per pfSense API v2 docs)
    reverse: bool = False

    def to_params(self) -> Dict[str, str]:
        """Convert to URL parameters"""
        params = {}
        if self.sort_by:
            params["sort_by"] = self.sort_by
            params["sort_order"] = self.sort_order
        if self.reverse:
            params["reverse"] = "true"
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
