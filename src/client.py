"""Enhanced pfSense API v2 client with advanced features."""

import asyncio
import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from urllib.parse import urlencode, urlparse

import httpx

from .models import (
    AuthMethod,
    ControlParameters,
    PaginationOptions,
    PfSenseVersion,
    QueryFilter,
    SortOptions,
)

logger = logging.getLogger(__name__)


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
        self.hateoas_enabled = enable_hateoas
        self.jwt_token = None
        self.jwt_expiry = None
        self.client = None
        self._client_loop = None

        # API base URL
        self.api_base = f"{self.host}/api/v2"

    def _ensure_client(self):
        """Ensure HTTP client is created for current event loop.

        When the event loop changes (e.g. between connection test and MCP server),
        the old httpx client is discarded. We don't attempt to close it from a
        different loop — httpx handles cleanup via garbage collection.
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # Recreate client if loop changed or client doesn't exist
        if self.client is None or self._client_loop != current_loop:
            # Discard the old client — it belongs to a different event loop
            # and cannot be safely closed from here. The explicit close()
            # method should be used before switching loops.
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
        """Get a new JWT token.

        The /auth/jwt endpoint requires Basic Auth credentials in the header,
        NOT username/password in the JSON body.
        """
        if not self.username or not self.password:
            raise ValueError("Username and password required for JWT auth")

        self._ensure_client()
        credentials = base64.b64encode(
            f"{self.username}:{self.password}".encode()
        ).decode()
        response = await self.client.post(
            f"{self.api_base}/auth/jwt",
            headers={"Authorization": f"Basic {credentials}"},
        )
        response.raise_for_status()
        data = response.json()

        token = data.get("data", {}).get("token") if isinstance(data.get("data"), dict) else None
        if not token:
            raise ValueError(
                "JWT token not returned by /auth/jwt endpoint. "
                "Response may be malformed or API version incompatible."
            )
        self.jwt_token = token
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
        extra_params: Optional[Dict[str, str]] = None,
    ) -> str:
        """Build query parameters for GET requests.

        NOTE: Control parameters (apply, placement, append, remove) are NOT
        included here. The pfSense API reads them from the JSON request body
        on POST/PATCH/DELETE, not from the query string. They are merged into
        the request body by _make_request().

        NOTE: HATEOAS is a server-side setting controlled via
        PATCH /system/restapi/settings. Per-request ?hateoas=true is NOT
        supported by the pfSense API, so it is not included here.
        """
        params = {}

        # Add filters
        if filters:
            for filter_obj in filters:
                key, value = filter_obj.to_param()
                params[key] = value

        # Add sorting
        if sort:
            params.update(sort.to_params())

        # Add pagination
        if pagination:
            params.update(pagination.to_params())

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
        extra_params: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict:
        """Make API request with enhanced features.

        Control parameters (apply, placement, append, remove) are merged into
        the JSON request body — pfSense REST API v2 reads them from the body
        on POST/PATCH/DELETE, not from query parameters.
        """
        # Ensure client is created for current event loop
        self._ensure_client()

        url = f"{self.api_base}{endpoint}"

        # Merge control parameters into request body (NOT query string)
        # pfSense API reads apply/placement/append/remove from request_data
        # which is the decoded JSON body for POST/PATCH/DELETE
        if control:
            control_dict = control.to_params()
            # Convert string "true"/"false" to actual booleans for JSON body
            body_params = {}
            for k, v in control_dict.items():
                if v == "true":
                    body_params[k] = True
                elif v == "false":
                    body_params[k] = False
                else:
                    # placement is an int
                    try:
                        body_params[k] = int(v)
                    except (ValueError, TypeError):
                        body_params[k] = v
            if data is not None:
                data = {**data, **body_params}
            else:
                data = body_params

        # Build query string (filters, sort, pagination — NOT control params)
        query_string = self._build_query_params(
            filters, sort, pagination, extra_params
        )
        if query_string:
            url += f"?{query_string}"

        # Log request (endpoint only — no query params that may contain sensitive data)
        logger.info("API Request: %s %s", method, endpoint)

        # Don't send Content-Type on GET or bodyless DELETE - pfSense API ignores
        # query params when Content-Type: application/json is present on bodyless requests
        needs_body = method.upper() in ("POST", "PATCH", "PUT") or (method.upper() == "DELETE" and data)
        headers = await self._get_auth_headers(include_content_type=needs_body)

        # Per-request timeout override (used by log endpoints to fail fast).
        # Only the read phase is shortened so connect/write/pool timeouts
        # keep using the client defaults and don't cause false positives.
        req_timeout = httpx.Timeout(self.timeout, read=timeout) if timeout else None

        # Make request
        if method.upper() == "GET":
            response = await self.client.get(url, headers=headers, timeout=req_timeout)
        elif method.upper() == "POST":
            response = await self.client.post(url, headers=headers, json=data, timeout=req_timeout)
        elif method.upper() == "PATCH":
            response = await self.client.patch(url, headers=headers, json=data, timeout=req_timeout)
        elif method.upper() == "PUT":
            response = await self.client.put(url, headers=headers, json=data, timeout=req_timeout)
        elif method.upper() == "DELETE":
            response = await self.client.delete(url, headers=headers, json=data, timeout=req_timeout)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # Enhanced error handling
        if response.status_code >= 400:
            error_body = response.text
            try:
                error_json = response.json()
                error_message = error_json.get('message', 'Unknown error')
                error_detail = json.dumps(error_json, indent=2)
            except Exception:
                error_message = error_body
                error_detail = error_body

            # Log error info at DEBUG level (endpoint only, no sensitive data)
            logger.debug(
                "API Error - Status: %s, Endpoint: %s, Method: %s",
                response.status_code, endpoint, method
            )
            logger.debug("Response: %s", error_detail)

            # Log concise error at ERROR level
            logger.error(f"pfSense API {response.status_code}: {error_message}")

            # Raise with error info (no request data to avoid leaking sensitive payloads)
            url_path = urlparse(url).path
            error_msg = (
                f"\n=== pfSense API Error ===\n"
                f"Status: {response.status_code}\n"
                f"Endpoint: {url_path}\n"
                f"Method: {method}\n"
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
        if pagination is None:
            pagination = PaginationOptions(limit=200)
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
            logger.debug("Remapping sort field 'sequence' to 'tracker' (pfSense API v2)")
            sort = SortOptions(sort_by="tracker", sort_order=sort.sort_order)

        if pagination is None:
            pagination = PaginationOptions(limit=200)
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

        return await self._make_request(
            "PATCH", "/firewall/rule",
            data={**updates, "id": rule_id}, control=control
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

        if pagination is None:
            pagination = PaginationOptions(limit=200)
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
            "PATCH", "/firewall/alias",
            data={"id": alias_id, "address": addresses},
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
            "PATCH", "/firewall/alias",
            data={"id": alias_id, "address": addresses},
            control=control
        )

    async def update_alias(
        self,
        alias_id: int,
        updates: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Update an alias by ID

        Args:
            alias_id: Alias ID (array index from GET /firewall/aliases)
            updates: Fields to update
            control: Control parameters (apply, etc.)
        """
        if not control:
            control = ControlParameters(apply=True)

        return await self._make_request(
            "PATCH", "/firewall/alias",
            data={**updates, "id": alias_id}, control=control
        )

    async def delete_alias(
        self,
        alias_id: int,
        apply_immediately: bool = True
    ) -> Dict:
        """Delete an alias by ID

        Args:
            alias_id: Alias ID (array index from GET /firewall/aliases)
            apply_immediately: Whether to apply changes
        """
        control = ControlParameters(apply=apply_immediately)

        return await self._make_request(
            "DELETE", "/firewall/alias",
            data={"id": alias_id}, control=control
        )

    # Enhanced Log Methods
    #
    # WARNING: pfSense REST API log endpoints load the entire log file into
    # memory before applying the limit parameter. On firewalls with large
    # logs this causes PHP to exceed its 512 MB memory limit and crash.
    # All log methods use a short timeout (LOG_TIMEOUT) to fail fast rather
    # than waiting for the server to OOM and drop the connection.
    #
    # Upstream tracking:
    #   Issue: https://github.com/jaredhendrickson13/pfsense-api/issues/806
    #   Fix:   https://github.com/jaredhendrickson13/pfsense-api/pull/860
    #
    # TODO(pfsense-log-oom-workaround, pfSense-pkg-RESTAPI#860): remove after
    # first release containing the upstream fix.
    LOG_TIMEOUT = 10  # seconds

    async def get_firewall_logs(
        self,
        lines: int = 20,
        filters: Optional[List[QueryFilter]] = None,
    ) -> Dict:
        """Get firewall logs with filtering (small limits to avoid memory issues).

        Note: Log endpoints do NOT support sort_by. The firewall log model only
        has a 'text' field — use QueryFilter("text", value, "contains") for filtering.
        """
        safe_lines = max(1, min(lines, 50))
        pagination = PaginationOptions(limit=safe_lines)

        return await self._make_request(
            "GET", "/status/logs/firewall",
            filters=filters, pagination=pagination,
            timeout=self.LOG_TIMEOUT,
        )

    async def get_logs_by_ip(self, ip_address: str, lines: int = 20) -> Dict:
        """Get firewall logs containing a specific IP address.

        Uses text__contains since the firewall log model only has a 'text' field.
        """
        filters = [QueryFilter("text", ip_address, "contains")]

        return await self.get_firewall_logs(
            filters=filters,
            lines=min(lines, 50)
        )

    async def get_blocked_traffic_logs(self, lines: int = 20) -> Dict:
        """Get firewall logs containing 'block' in the raw text.

        Uses text__contains since the firewall log model only has a 'text' field.
        """
        filters = [QueryFilter("text", "block", "contains")]

        return await self.get_firewall_logs(
            filters=filters,
            lines=min(lines, 50)
        )

    # Allowlist of valid log types to prevent path traversal via log endpoint
    _VALID_LOG_TYPES = frozenset({"firewall", "system", "dhcp", "openvpn", "auth"})

    async def get_logs(
        self,
        log_type: str,
        lines: int = 20,
        filters: Optional[List[QueryFilter]] = None,
    ) -> Dict:
        """Get logs of any type. Log endpoints do NOT support sort_by.

        Valid log_type values: firewall, system, dhcp, openvpn, auth
        """
        log_type = log_type.lower().strip()
        if log_type not in self._VALID_LOG_TYPES:
            raise ValueError(
                f"Invalid log type '{log_type}'. "
                f"Allowed: {', '.join(sorted(self._VALID_LOG_TYPES))}"
            )
        safe_lines = max(1, min(lines, 50))
        pagination = PaginationOptions(limit=safe_lines)
        endpoint = f"/status/logs/{log_type}"
        return await self._make_request(
            "GET", endpoint,
            filters=filters, pagination=pagination,
            timeout=self.LOG_TIMEOUT,
        )

    # Enhanced Service Methods

    async def get_services(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get services with filtering"""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        return await self._make_request(
            "GET", "/status/services",
            filters=filters, sort=sort, pagination=pagination
        )

    async def find_running_services(self) -> Dict:
        """Find only running services"""
        filters = [QueryFilter("status", "running")]
        return await self.get_services(filters=filters)

    async def find_stopped_services(self) -> Dict:
        """Find only stopped services"""
        filters = [QueryFilter("status", "stopped")]
        return await self.get_services(filters=filters)

    async def _lookup_service_id(self, service_name: str) -> int:
        """Look up a service's array index by name.

        The POST /status/service endpoint requires the service's integer 'id'
        (array index), not the service name. The 'name' field is read-only.
        """
        # Fetch all services so we can show available names on failure
        result = await self.get_services()
        services = result.get("data") or []
        for svc in services:
            if svc.get("name") == service_name:
                svc_id = svc.get("id")
                if svc_id is not None:
                    return int(svc_id)
        available = sorted(set(s.get("name") for s in services if s.get("name")))
        raise ValueError(
            f"Service '{service_name}' not found. "
            f"Available services: {', '.join(available)}"
        )

    async def start_service(self, service_name: str) -> Dict:
        """Start a service by name"""
        svc_id = await self._lookup_service_id(service_name)
        return await self._make_request(
            "POST", "/status/service",
            data={"id": svc_id, "action": "start"}
        )

    async def stop_service(self, service_name: str) -> Dict:
        """Stop a service by name"""
        svc_id = await self._lookup_service_id(service_name)
        return await self._make_request(
            "POST", "/status/service",
            data={"id": svc_id, "action": "stop"}
        )

    async def restart_service(self, service_name: str) -> Dict:
        """Restart a service by name"""
        svc_id = await self._lookup_service_id(service_name)
        return await self._make_request(
            "POST", "/status/service",
            data={"id": svc_id, "action": "restart"}
        )

    # Enhanced DHCP Methods

    async def get_dhcp_leases(
        self,
        interface: Optional[str] = None,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get DHCP leases with filtering"""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
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

    # DHCP Static Mapping Methods

    async def get_dhcp_static_mappings(
        self,
        interface: Optional[str] = None,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get DHCP static mappings with filtering

        Args:
            interface: Parent DHCP server interface (e.g. "lan", "opt1").
                       Passed as parent_id query param, not a filter.
        """
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        extra = {"parent_id": interface} if interface else None
        return await self._make_request(
            "GET", "/services/dhcp_server/static_mappings",
            filters=filters, sort=sort, pagination=pagination,
            extra_params=extra
        )

    async def create_dhcp_static_mapping(
        self,
        mapping_data: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Create a DHCP static mapping

        Args:
            mapping_data: Mapping data including parent_id, mac, ipaddr, hostname, etc.
            control: Control parameters (apply, etc.)
        """
        if not control:
            control = ControlParameters(apply=True)

        return await self._make_request(
            "POST", "/services/dhcp_server/static_mapping",
            data=mapping_data, control=control
        )

    async def update_dhcp_static_mapping(
        self,
        mapping_id: int,
        updates: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Update a DHCP static mapping by ID

        Args:
            mapping_id: Mapping ID
            updates: Fields to update
            control: Control parameters (apply, etc.)
        """
        if not control:
            control = ControlParameters(apply=True)

        return await self._make_request(
            "PATCH", "/services/dhcp_server/static_mapping",
            data={**updates, "id": mapping_id}, control=control
        )

    async def delete_dhcp_static_mapping(
        self,
        mapping_id: int,
        parent_id: str,
        apply_immediately: bool = True
    ) -> Dict:
        """Delete a DHCP static mapping by ID

        Args:
            mapping_id: Mapping ID
            parent_id: Parent interface (e.g., "lan") - required by pfSense API
            apply_immediately: Whether to apply changes
        """
        control = ControlParameters(apply=apply_immediately)

        return await self._make_request(
            "DELETE", "/services/dhcp_server/static_mapping",
            data={"id": mapping_id, "parent_id": parent_id}, control=control
        )

    # NAT Port Forward Methods

    async def get_nat_port_forwards(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get NAT port forwarding rules with filtering"""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        return await self._make_request(
            "GET", "/firewall/nat/port_forwards",
            filters=filters, sort=sort, pagination=pagination
        )

    async def create_nat_port_forward(
        self,
        forward_data: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Create a NAT port forward rule"""
        if not control:
            control = ControlParameters(apply=True)
        return await self._make_request(
            "POST", "/firewall/nat/port_forward",
            data=forward_data, control=control
        )

    async def update_nat_port_forward(
        self,
        port_forward_id: int,
        updates: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Update a NAT port forward rule"""
        if not control:
            control = ControlParameters(apply=True)
        return await self._make_request(
            "PATCH", "/firewall/nat/port_forward",
            data={**updates, "id": port_forward_id}, control=control
        )

    async def delete_nat_port_forward(
        self,
        port_forward_id: int,
        apply_immediately: bool = True
    ) -> Dict:
        """Delete a NAT port forward rule"""
        control = ControlParameters(apply=apply_immediately)
        return await self._make_request(
            "DELETE", "/firewall/nat/port_forward",
            data={"id": port_forward_id}, control=control
        )

    # Firewall Apply

    async def apply_firewall_changes(self) -> Dict:
        """Force apply pending firewall changes (triggers filter_configure)"""
        return await self._make_request("POST", "/firewall/apply", data={})

    # DHCP Server Configuration

    async def get_dhcp_servers(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get DHCP server configurations for all interfaces"""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        return await self._make_request(
            "GET", "/services/dhcp_servers",
            filters=filters, sort=sort, pagination=pagination
        )

    async def update_dhcp_server(
        self,
        updates: Dict,
        control: Optional[ControlParameters] = None
    ) -> Dict:
        """Update DHCP server configuration

        Args:
            updates: Fields to update (must include id for the target server)
            control: Control parameters (apply, etc.)
        """
        if not control:
            control = ControlParameters(apply=True)

        return await self._make_request(
            "PATCH", "/services/dhcp_server",
            data=updates, control=control
        )

    # ARP Table

    async def get_arp_table(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None
    ) -> Dict:
        """Get ARP table entries"""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        return await self._make_request(
            "GET", "/diagnostics/arp_table",
            filters=filters, sort=sort, pagination=pagination
        )

    # Diagnostic Commands

    # Allowlist of safe diagnostic commands — NEVER add user-supplied commands
    _ALLOWED_DIAGNOSTIC_COMMANDS = frozenset({
        "cat /tmp/rules.debug",
    })

    async def _run_diagnostic_command(self, command: str) -> Dict:
        """Run a diagnostic shell command on pfSense (internal use only).

        This method is intentionally private AND restricted to an allowlist
        to prevent arbitrary command execution on the pfSense appliance.

        Args:
            command: Shell command to execute (must be in _ALLOWED_DIAGNOSTIC_COMMANDS)

        Raises:
            ValueError: If the command is not in the allowlist
        """
        if command not in self._ALLOWED_DIAGNOSTIC_COMMANDS:
            raise ValueError(
                f"Command not permitted. Allowed commands: "
                f"{', '.join(sorted(self._ALLOWED_DIAGNOSTIC_COMMANDS))}"
            )
        return await self._make_request(
            "POST", "/diagnostics/command_prompt",
            data={"command": command}
        )

    # Generic CRUD Methods
    # Used by new tool modules to avoid adding domain-specific methods
    # for every endpoint. Existing domain methods (get_firewall_rules, etc.)
    # remain as-is for backward compatibility.

    async def crud_list(
        self,
        endpoint: str,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """Generic list/search for any plural endpoint."""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        return await self._make_request(
            "GET", endpoint,
            filters=filters, sort=sort, pagination=pagination,
            extra_params=extra_params,
        )

    async def crud_create(
        self,
        endpoint: str,
        data: Dict,
        control: Optional[ControlParameters] = None,
    ) -> Dict:
        """Generic create for any singular endpoint."""
        if control is None:
            control = ControlParameters(apply=True)
        return await self._make_request(
            "POST", endpoint, data=data, control=control,
        )

    async def crud_update(
        self,
        endpoint: str,
        obj_id: Union[int, str],
        updates: Dict,
        control: Optional[ControlParameters] = None,
    ) -> Dict:
        """Generic update for any singular endpoint."""
        if control is None:
            control = ControlParameters(apply=True)
        return await self._make_request(
            "PATCH", endpoint,
            data={**updates, "id": obj_id}, control=control,
        )

    async def crud_delete(
        self,
        endpoint: str,
        obj_id: Union[int, str],
        control: Optional[ControlParameters] = None,
        extra_data: Optional[Dict] = None,
    ) -> Dict:
        """Generic delete for any singular endpoint."""
        if control is None:
            control = ControlParameters(apply=True)
        data = {}
        if extra_data:
            data.update(extra_data)
        # Ensure id is never overridden by extra_data
        data["id"] = obj_id
        return await self._make_request(
            "DELETE", endpoint, data=data, control=control,
        )

    async def crud_apply(self, endpoint: str) -> Dict:
        """Generic apply for any apply endpoint (POST with empty body)."""
        return await self._make_request("POST", endpoint, data={})

    async def crud_get_settings(self, endpoint: str) -> Dict:
        """Generic GET for singleton settings endpoints."""
        return await self._make_request("GET", endpoint)

    async def crud_update_settings(
        self,
        endpoint: str,
        updates: Dict,
        control: Optional[ControlParameters] = None,
    ) -> Dict:
        """Generic PATCH for singleton settings endpoints."""
        if control is None:
            control = ControlParameters(apply=True)
        return await self._make_request(
            "PATCH", endpoint, data=updates, control=control,
        )

    # Object ID Management

    async def refresh_object_ids(self, endpoint: str) -> Dict:
        """Refresh object IDs by re-querying endpoint"""
        pagination = PaginationOptions(limit=200)
        return await self._make_request("GET", endpoint, pagination=pagination)

    async def find_object_by_field(
        self,
        endpoint: str,
        field: str,
        value: str
    ) -> Optional[Dict]:
        """Find object by specific field value (handles ID changes)"""
        filters = [QueryFilter(field, value)]
        pagination = PaginationOptions(limit=50)
        result = await self._make_request(
            "GET", endpoint,
            filters=filters, pagination=pagination
        )

        data = result.get("data") or []
        return data[0] if data else None

    # Stale-ID Guard

    async def verify_object_id(
        self,
        endpoint: str,
        object_id: int,
        field: str,
        expected_value: str,
    ) -> Optional[str]:
        """Verify an object ID still points to the expected object.

        Returns None if verified, or an error message if the ID is stale.
        """
        try:
            filters = [QueryFilter("id", str(object_id))]
            result = await self._make_request(
                "GET", endpoint,
                filters=filters,
                pagination=PaginationOptions(limit=1),
            )
            data = result.get("data") or []
            if not data:
                return f"Object with ID {object_id} not found at {endpoint}. IDs may have shifted after a deletion."
            obj = data[0]
            actual = str(obj.get(field, ""))
            if actual != str(expected_value):
                return (
                    f"ID {object_id} does not match expected {field}='{expected_value}' "
                    f"(actual: '{actual}'). IDs may have shifted — re-query before operating."
                )
        except Exception as e:
            return f"Failed to verify object ID: {e}"
        return None

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

        return await self._make_request("GET", endpoint)

    # Utility Methods

    async def test_connection(self) -> Dict:
        """Test API connection.

        Returns:
            Dict with 'connected' (bool) and 'error' (str, if failed).
        """
        try:
            await self.get_system_status()
            return {"connected": True}
        except httpx.ConnectError as e:
            return {"connected": False, "error": f"Cannot reach {self.host}: {e}"}
        except httpx.TimeoutException:
            return {"connected": False, "error": f"Connection to {self.host} timed out after {self.timeout}s"}
        except Exception as e:
            error_str = str(e)
            if "401" in error_str:
                return {"connected": False, "error": "Authentication failed (401). Check your API key or credentials."}
            if "403" in error_str:
                return {"connected": False, "error": "Access denied (403). API user may lack required privileges."}
            if "404" in error_str:
                return {"connected": False, "error": "API endpoint not found (404). Is the pfSense REST API v2 package installed?"}
            if "SSL" in error_str or "certificate" in error_str.lower():
                return {"connected": False, "error": f"SSL/TLS error: {e}. Try setting VERIFY_SSL=false for self-signed certs."}
            return {"connected": False, "error": str(e)}

    async def get_api_capabilities(self) -> Dict:
        """Get API capabilities and settings"""
        return await self._make_request("GET", "/system/restapi/settings")

    async def set_hateoas(self, enabled: bool) -> Dict:
        """Enable or disable HATEOAS on the pfSense REST API server.

        HATEOAS is a global server-side setting, NOT a per-request toggle.
        This calls PATCH /system/restapi/settings to change it.
        """
        result = await self._make_request(
            "PATCH", "/system/restapi/settings",
            data={"hateoas": enabled},
        )
        self.hateoas_enabled = enabled
        return result

    # ------------------------------------------------------------------ #
    # User Management
    # ------------------------------------------------------------------ #

    async def get_users(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None,
    ) -> Dict:
        """Get users with optional filtering"""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        return await self._make_request(
            "GET", "/users",
            filters=filters, sort=sort, pagination=pagination,
        )

    async def create_user(self, user_data: Dict) -> Dict:
        """Create a new user"""
        return await self._make_request("POST", "/user", data=user_data)

    async def update_user(self, user_data: Dict) -> Dict:
        """Update an existing user"""
        return await self._make_request("PATCH", "/user", data=user_data)

    async def delete_user(self, user_id: int) -> Dict:
        """Delete a user by ID"""
        return await self._make_request("DELETE", "/user", data={"id": user_id})

    # ------------------------------------------------------------------ #
    # Group Management
    # ------------------------------------------------------------------ #

    async def get_groups(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None,
    ) -> Dict:
        """Get user groups with optional filtering"""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        return await self._make_request(
            "GET", "/user/groups",
            filters=filters, sort=sort, pagination=pagination,
        )

    async def create_group(self, group_data: Dict) -> Dict:
        """Create a new user group"""
        return await self._make_request("POST", "/user/group", data=group_data)

    async def update_group(self, group_data: Dict) -> Dict:
        """Update an existing user group"""
        return await self._make_request("PATCH", "/user/group", data=group_data)

    async def delete_group(self, group_id: int) -> Dict:
        """Delete a user group by ID"""
        return await self._make_request("DELETE", "/user/group", data={"id": group_id})

    # ------------------------------------------------------------------ #
    # Auth Server Management
    # ------------------------------------------------------------------ #

    async def get_auth_servers(
        self,
        filters: Optional[List[QueryFilter]] = None,
        sort: Optional[SortOptions] = None,
        pagination: Optional[PaginationOptions] = None,
    ) -> Dict:
        """Get authentication servers with optional filtering"""
        if pagination is None:
            pagination = PaginationOptions(limit=200)
        return await self._make_request(
            "GET", "/user/auth_servers",
            filters=filters, sort=sort, pagination=pagination,
        )

    async def create_auth_server(self, server_data: Dict) -> Dict:
        """Create a new authentication server"""
        return await self._make_request("POST", "/user/auth_server", data=server_data)

    async def update_auth_server(self, server_data: Dict) -> Dict:
        """Update an existing authentication server"""
        return await self._make_request("PATCH", "/user/auth_server", data=server_data)

    async def delete_auth_server(self, auth_server_id: int) -> Dict:
        """Delete an authentication server by ID"""
        return await self._make_request("DELETE", "/user/auth_server", data={"id": auth_server_id})

    async def close(self):
        """Close HTTP client and reset state"""
        if self.client is not None:
            await self.client.aclose()
        self.reset()

    def reset(self):
        """Reset client state for reuse in a new event loop."""
        self.client = None
        self._client_loop = None
