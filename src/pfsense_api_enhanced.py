#!/usr/bin/env python3
"""
Enhanced pfSense API v2 Integration Module
Implements advanced features: Object IDs, Queries/Filters, HATEOAS, Control Parameters
Compatible with jaredhendrickson13/pfsense-api package
"""

import os
import json
import base64
import re
import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass
import httpx
from datetime import datetime, timedelta
from urllib.parse import urlencode

# Configure logger
logger = logging.getLogger(__name__)

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

class EnhancedPfSenseAPIClient:
    """
    Enhanced pfSense API v2 Client with advanced features
    """

    def __init__(
        self,
        host: str,
        auth_method: AuthMethod = AuthMethod.API_KEY,
        username: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
        version: PfSenseVersion = PfSenseVersion.CE_2_8_0,
        enable_hateoas: bool = False
    ):
        self.host = host.rstrip('/')
        self.auth_method = auth_method
        self.username = username
        self.password = password
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.version = version
        self.enable_hateoas = enable_hateoas
        self.jwt_token = None
        self.jwt_expiry = None
        self.client = None
        self._client_loop = None

        # API base URL
        self.api_base = f"{self.host}/api/v2"

    def _ensure_client(self):
        """Ensure HTTP client is created for current event loop"""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # Recreate client if loop changed or client doesn't exist
        if self.client is None or self._client_loop != current_loop:
            if self.client is not None:
                # Close old client if it exists
                try:
                    asyncio.create_task(self.client.aclose())
                except:
                    pass

            self.client = httpx.AsyncClient(
                verify=self.verify_ssl,
                timeout=self.timeout,
                follow_redirects=True
            )
            self._client_loop = current_loop

    async def _get_auth_headers(self, include_content_type: bool = True) -> Dict[str, str]:
        """Generate authentication headers based on auth method"""
        headers = {}
        if include_content_type:
            headers["Content-Type"] = "application/json"

        if self.auth_method == AuthMethod.BASIC:
            if not self.username or not self.password:
                raise ValueError("Username and password required for basic auth")
            credentials = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {credentials}"

        elif self.auth_method == AuthMethod.API_KEY:
            if not self.api_key:
                raise ValueError("API key required for API key auth")
            headers["X-API-Key"] = self.api_key

        elif self.auth_method == AuthMethod.JWT:
            if not self.jwt_token or self._is_jwt_expired():
                await self._refresh_jwt()
            headers["Authorization"] = f"Bearer {self.jwt_token}"

        return headers

    async def _refresh_jwt(self):
        """Get a new JWT token"""
        if not self.username or not self.password:
            raise ValueError("Username and password required for JWT auth")

        response = await self.client.post(
            f"{self.api_base}/auth/jwt",
            json={"username": self.username, "password": self.password}
        )
        response.raise_for_status()
        data = response.json()

        self.jwt_token = data.get("data", {}).get("token")
        self.jwt_expiry = datetime.now() + timedelta(hours=1)

    def _is_jwt_expired(self) -> bool:
        """Check if JWT token is expired"""
        if not self.jwt_expiry:
            return True
        return datetime.now() >= self.jwt_expiry

    def _build_query_params(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None,
        control: Optional[ControlParameters] = None,
        extra_params: Optional[Dict[str, str]] = None
    ) -> str:
        """Build query parameters for requests"""
        params = {}

        # Add filters
        if filters:
            for filter_obj in filters:
                key, value = filter_obj.to_param().split("=", 1)
                params[key] = value

        # Add sorting
        if sort:
            params.update(sort.to_params())

        # Add pagination
        if pagination:
            params.update(pagination.to_params())

        # Add control parameters
        if control:
            params.update(control.to_params())

        # Add HATEOAS
        if self.enable_hateoas:
            params["hateoas"] = "true"

        # Add extra parameters
        if extra_params:
            params.update(extra_params)

        return urlencode(params) if params else ""

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None,
        control: Optional[ControlParameters] = None,
        extra_params: Optional[Dict[str, str]] = None
    ) -> Dict:
        """Make API request with enhanced features"""
        # Ensure client is created for current event loop
        self._ensure_client()

        url = f"{self.api_base}{endpoint}"

        # Build query string
        query_string = self._build_query_params(
            filters, sort, pagination, control, extra_params
        )
        if query_string:
            url += f"?{query_string}"

        # Log the full URL being requested
        logger.info(f"API Request: {method} {url}")

        # Don't send Content-Type on GET/DELETE - pfSense API ignores query params
        # when Content-Type: application/json is present on bodyless requests
        needs_body = method.upper() in ("POST", "PATCH", "PUT")
        headers = await self._get_auth_headers(include_content_type=needs_body)

        # Make request
        if method.upper() == "GET":
            response = await self.client.get(url, headers=headers)
        elif method.upper() == "POST":
            response = await self.client.post(url, headers=headers, json=data)
        elif method.upper() == "PATCH":
            response = await self.client.patch(url, headers=headers, json=data)
        elif method.upper() == "PUT":
            response = await self.client.put(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            response = await self.client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Enhanced error handling
        if response.status_code >= 400:
            error_body = response.text
            try:
                error_json = response.json()
                error_message = error_json.get('message', 'Unknown error')
                error_detail = json.dumps(error_json, indent=2)
            except:
                error_message = error_body
                error_detail = error_body

            # Log detailed error info at DEBUG level
            logger.debug(
                f"API Error - Status: {response.status_code}, "
                f"URL: {url}, Method: {method}"
            )
            logger.debug(f"Request Data: {json.dumps(data, indent=2) if data else 'None'}")
            logger.debug(f"Response: {error_detail}")

            # Log concise error at ERROR level
            logger.error(f"pfSense API {response.status_code}: {error_message}")

            # Raise with detailed error message for debugging
            error_msg = (
                f"\n=== pfSense API Error ===\n"
                f"Status: {response.status_code}\n"
                f"URL: {url}\n"
                f"Method: {method}\n"
                f"Request Data: {json.dumps(data, indent=2) if data else 'None'}\n"
                f"Response: {error_detail}\n"
                f"========================\n"
            )
            raise Exception(error_msg)

        # Log successful request
        logger.debug(f"API Success: {method} {endpoint} - Status {response.status_code}")
        return response.json()

    # Enhanced System Methods

    async def get_system_status(self) -> Dict:
        """Get system status information"""
        return await self._make_request("GET", "/status/system")

    async def get_interfaces(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get interfaces with advanced filtering and sorting"""
        return await self._make_request(
            "GET", "/status/interfaces",
            filters=filters, sort=sort, pagination=pagination
        )

    async def find_interfaces_by_status(self, status: str) -> Dict:
        """Find interfaces by status (up, down, etc.)"""
        filters = [QueryFilter("status", status)]
        return await self.get_interfaces(filters=filters)

    async def search_interfaces(self, search_term: str) -> Dict:
        """Search interfaces by name or description"""
        filters = [
            QueryFilter("name", search_term, "contains")
        ]
        return await self.get_interfaces(filters=filters)

    # Enhanced Firewall Methods

    async def get_firewall_rules(
        self,
        interface: Optional[str] = None,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get firewall rules with advanced filtering"""
        # Interface field is an array in pfSense API v2, use contains operator
        if interface and not filters:
            filters = [QueryFilter("interface", interface, "contains")]
        elif interface and filters:
            filters.append(QueryFilter("interface", interface, "contains"))

        # 'sequence' is not a valid model field; use 'tracker' for rule ordering
        if sort and sort.sort_by == "sequence":
            sort = SortOptions(sort_by="tracker", sort_order=sort.sort_order)

        return await self._make_request(
            "GET", "/firewall/rules",
            filters=filters, sort=sort, pagination=pagination
        )

    async def find_rules_by_source(self, source_ip: str) -> Dict:
        """Find firewall rules by source IP"""
        filters = [QueryFilter("source", source_ip, "contains")]
        return await self.get_firewall_rules(filters=filters)

    async def find_rules_by_destination_port(self, port: Union[int, str]) -> Dict:
        """Find firewall rules by destination port"""
        filters = [QueryFilter("destination_port", str(port))]
        return await self.get_firewall_rules(filters=filters)

    async def find_blocked_rules(self) -> Dict:
        """Find all block/reject rules"""
        filters = [QueryFilter("type", "block|reject", "regex")]
        return await self.get_firewall_rules(filters=filters)

    async def get_rules_sorted_by_priority(self, interface: Optional[str] = None) -> Dict:
        """Get rules sorted by their order/priority"""
        sort = SortOptions(sort_by="tracker", sort_order="SORT_ASC")
        return await self.get_firewall_rules(interface=interface, sort=sort)

    async def create_firewall_rule(
        self,
        rule_data: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Create firewall rule with control parameters"""
        if not control:
            control = ControlParameters(apply=True)

        return await self._make_request(
            "POST", "/firewall/rule",
            data=rule_data, control=control
        )

    async def update_firewall_rule(
        self,
        rule_id: int,
        updates: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Update firewall rule with control parameters

        Args:
            rule_id: Rule ID (array index from GET /firewall/rules)
            updates: Fields to update
            control: Control parameters (apply, etc.)
        """
        if not control:
            control = ControlParameters(apply=True)

        # Add id to the updates
        updates["id"] = rule_id

        return await self._make_request(
            "PATCH", "/firewall/rule",
            data=updates, control=control
        )

    async def move_firewall_rule(
        self,
        rule_id: int,
        new_position: int,
        apply_immediately: bool = True
    ) -> Dict:
        """Move firewall rule to new position

        Args:
            rule_id: Rule ID (array index from GET /firewall/rules)
            new_position: New position in rule list
            apply_immediately: Whether to apply changes
        """
        control = ControlParameters(
            placement=new_position,
            apply=apply_immediately
        )

        return await self._make_request(
            "PATCH", "/firewall/rule",
            data={"id": rule_id}, control=control
        )

    async def delete_firewall_rule(
        self,
        rule_id: int,
        apply_immediately: bool = True
    ) -> Dict:
        """Delete firewall rule

        Args:
            rule_id: Rule ID (array index from GET /firewall/rules)
            apply_immediately: Whether to apply changes
        """
        control = ControlParameters(apply=apply_immediately)

        return await self._make_request(
            "DELETE", "/firewall/rule",
            data={"id": rule_id}, control=control
        )

    # Enhanced Alias Methods

    async def get_aliases(
        self,
        alias_type: Optional[str] = None,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get aliases with filtering"""
        if alias_type and not filters:
            filters = [QueryFilter("type", alias_type)]
        elif alias_type and filters:
            filters.append(QueryFilter("type", alias_type))

        return await self._make_request(
            "GET", "/firewall/aliases",
            filters=filters, sort=sort, pagination=pagination
        )

    async def find_aliases_containing_ip(self, ip_address: str) -> Dict:
        """Find aliases that contain a specific IP"""
        filters = [QueryFilter("address", ip_address, "contains")]
        return await self.get_aliases(filters=filters)

    async def search_aliases(self, search_term: str) -> Dict:
        """Search aliases by name or description"""
        filters = [
            QueryFilter("name", search_term, "contains")
        ]
        return await self.get_aliases(filters=filters)

    async def create_alias(
        self,
        alias_data: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Create alias with control parameters"""
        if not control:
            control = ControlParameters(apply=True)

        return await self._make_request(
            "POST", "/firewall/alias",
            data=alias_data, control=control
        )

    async def add_to_alias(
        self,
        alias_id: int,
        addresses: List[str]
    ) -> Dict:
        """Add addresses to existing alias"""
        control = ControlParameters(append=True, apply=True)

        return await self._make_request(
            "PATCH", f"/firewall/alias/{alias_id}",
            data={"address": addresses},
            control=control
        )

    async def remove_from_alias(
        self,
        alias_id: int,
        addresses: List[str]
    ) -> Dict:
        """Remove addresses from existing alias"""
        control = ControlParameters(remove=True, apply=True)

        return await self._make_request(
            "PATCH", f"/firewall/alias/{alias_id}",
            data={"address": addresses},
            control=control
        )

    # Enhanced Log Methods

    async def get_firewall_logs(
        self,
        lines: int = 20,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None
    ) -> Dict:
        """Get firewall logs with filtering (small limits to avoid memory issues)"""
        # Cap limit to avoid pfSense PHP memory exhaustion
        safe_lines = min(lines, 50)
        pagination = PaginationOptions(limit=safe_lines)

        return await self._make_request(
            "GET", "/status/logs/firewall",
            filters=filters, sort=sort, pagination=pagination
        )

    async def get_logs_by_ip(self, ip_address: str, lines: int = 20) -> Dict:
        """Get logs for specific IP address"""
        filters = [QueryFilter("src_ip", ip_address)]

        return await self.get_firewall_logs(
            filters=filters,
            lines=min(lines, 50)
        )

    async def get_blocked_traffic_logs(self, lines: int = 20) -> Dict:
        """Get logs of blocked traffic"""
        filters = [QueryFilter("action", "block")]

        return await self.get_firewall_logs(
            filters=filters,
            lines=min(lines, 50)
        )

    # Enhanced Service Methods

    async def get_services(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None
    ) -> Dict:
        """Get services with filtering"""
        return await self._make_request(
            "GET", "/status/services",
            filters=filters, sort=sort
        )

    async def find_running_services(self) -> Dict:
        """Find only running services"""
        filters = [QueryFilter("status", "running")]
        return await self.get_services(filters=filters)

    async def find_stopped_services(self) -> Dict:
        """Find only stopped services"""
        filters = [QueryFilter("status", "stopped")]
        return await self.get_services(filters=filters)

    # Enhanced DHCP Methods

    async def get_dhcp_leases(
        self,
        interface: Optional[str] = None,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get DHCP leases with filtering"""
        # DHCP field is 'if' not 'interface'
        if interface and not filters:
            filters = [QueryFilter("if", interface, "contains")]
        elif interface and filters:
            filters.append(QueryFilter("if", interface, "contains"))

        return await self._make_request(
            "GET", "/status/dhcp_server/leases",
            filters=filters, sort=sort, pagination=pagination
        )

    async def find_lease_by_mac(self, mac_address: str) -> Dict:
        """Find DHCP lease by MAC address"""
        filters = [QueryFilter("mac", mac_address)]
        return await self.get_dhcp_leases(filters=filters)

    async def find_lease_by_hostname(self, hostname: str) -> Dict:
        """Find DHCP lease by hostname"""
        filters = [QueryFilter("hostname", hostname, "contains")]
        return await self.get_dhcp_leases(filters=filters)

    async def get_active_leases(self) -> Dict:
        """Get only active DHCP leases"""
        filters = [QueryFilter("active_status", "active")]
        sort = SortOptions(sort_by="starts", sort_order="SORT_DESC")
        return await self.get_dhcp_leases(filters=filters, sort=sort)

    # Object ID Management

    async def refresh_object_ids(self, endpoint: str) -> Dict:
        """Refresh object IDs by re-querying endpoint"""
        return await self._make_request("GET", endpoint)

    async def find_object_by_field(
        self,
        endpoint: str,
        field: str,
        value: str
    ) -> Optional[Dict]:
        """Find object by specific field value (handles ID changes)"""
        filters = [QueryFilter(field, value)]
        result = await self._make_request(
            "GET", endpoint,
            filters=filters
        )

        data = result.get("data", [])
        return data[0] if data else None

    # HATEOAS Navigation

    def extract_links(self, response: Dict) -> Dict[str, str]:
        """Extract HATEOAS links from response"""
        return response.get("_links", {})

    async def follow_link(self, link_url: str) -> Dict:
        """Follow a HATEOAS link"""
        # Remove base URL if present
        if link_url.startswith(self.host):
            endpoint = link_url.replace(self.host, "").replace("/api/v2", "")
        else:
            endpoint = link_url

        headers = await self._get_auth_headers()
        response = await self.client.get(f"{self.api_base}{endpoint}", headers=headers)
        response.raise_for_status()
        return response.json()

    # Utility Methods

    async def test_connection(self) -> bool:
        """Test API connection"""
        try:
            await self.get_system_status()
            return True
        except Exception:
            return False

    async def get_api_capabilities(self) -> Dict:
        """Get API capabilities and settings"""
        return await self._make_request("GET", "/system/restapi/settings")

    async def enable_hateoas(self) -> Dict:
        """Enable HATEOAS for this session"""
        self.enable_hateoas = True
        return {"message": "HATEOAS enabled for this session"}

    async def disable_hateoas(self) -> Dict:
        """Disable HATEOAS for this session"""
        self.enable_hateoas = False
        return {"message": "HATEOAS disabled for this session"}

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Helper functions for common query patterns

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


# Example usage
if __name__ == "__main__":
    import asyncio

    async def example_usage():
        client = EnhancedPfSenseAPIClient(
            host="https://pfsense.example.com",
            auth_method=AuthMethod.API_KEY,
            api_key="your-api-key",
            enable_hateoas=True
        )

        # Example: Find all firewall rules blocking port 22
        port_22_blocks = await client.find_rules_by_destination_port(22)

        # Example: Get recent blocked traffic
        recent_blocks = await client.get_blocked_traffic_logs(lines=50)

        # Example: Find DHCP lease by MAC address
        lease = await client.find_lease_by_mac("aa:bb:cc:dd:ee:ff")

        # Example: Search interfaces containing "wan"
        wan_interfaces = await client.search_interfaces("wan")

        await client.close()

    # asyncio.run(example_usage())
