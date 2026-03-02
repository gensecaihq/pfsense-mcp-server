"""
Enhanced pfSense MCP Server
Advanced pfSense management via Model Context Protocol
"""

__version__ = "4.0.0"
__author__ = "pfSense MCP Server Team"
__description__ = "Advanced pfSense management with filtering, sorting, and HATEOAS support"

from .client import EnhancedPfSenseAPIClient
from .models import (
    AuthMethod,
    ControlParameters,
    PaginationOptions,
    PfSenseVersion,
    QueryFilter,
    SortOptions,
)
from .server import get_api_client, mcp

__all__ = [
    "mcp",
    "get_api_client",
    "EnhancedPfSenseAPIClient",
    "AuthMethod",
    "PfSenseVersion",
    "QueryFilter",
    "SortOptions",
    "PaginationOptions",
    "ControlParameters"
]
