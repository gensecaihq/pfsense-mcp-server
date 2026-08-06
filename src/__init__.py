"""
Enhanced pfSense MCP Server
Advanced pfSense management via Model Context Protocol
"""

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
from .server import VERSION, get_api_client, mcp

# Single source of truth for the version: server.VERSION.
__version__ = VERSION

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
