"""
Enhanced pfSense MCP Server
Advanced pfSense management via Model Context Protocol
"""

__version__ = "4.0.0"
__author__ = "pfSense MCP Server Team"
__description__ = "Advanced pfSense management with filtering, sorting, and HATEOAS support"

from .main import mcp, get_api_client
from .pfsense_api_enhanced import (
    EnhancedPfSenseAPIClient,
    AuthMethod,
    PfSenseVersion,
    QueryFilter,
    SortOptions,
    PaginationOptions,
    ControlParameters
)

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