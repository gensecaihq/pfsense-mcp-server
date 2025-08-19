#!/usr/bin/env python3
"""
pfSense API v2 Integration Module
Compatible with jaredhendrickson13/pfsense-api package
Supports pfSense CE 2.8.0 and pfSense Plus 24.11
"""

import os
import json
import base64
import hashlib
import time
from typing import Dict, List, Optional, Any
from enum import Enum
import httpx
from datetime import datetime, timedelta

class PfSenseVersion(str, Enum):
    CE_2_8_0 = "2.8.0"
    PLUS_24_11 = "24.11"

class AuthMethod(str, Enum):
    BASIC = "basic"
    API_KEY = "api_key"
    JWT = "jwt"

class PfSenseAPIv2Client:
    """
    Client for pfSense REST API v2 (jaredhendrickson13/pfsense-api)
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
        version: PfSenseVersion = PfSenseVersion.CE_2_8_0
    ):
        self.host = host.rstrip('/')
        self.auth_method = auth_method
        self.username = username
        self.password = password
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.version = version
        self.jwt_token = None
        self.jwt_expiry = None
        
        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            verify=verify_ssl,
            timeout=timeout,
            follow_redirects=True
        )
        
        # API base URL
        self.api_base = f"{self.host}/api/v2"
        
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers based on auth method"""
        headers = {"Content-Type": "application/json"}
        
        if self.auth_method == AuthMethod.BASIC:
            # Basic authentication
            if not self.username or not self.password:
                raise ValueError("Username and password required for basic auth")
            credentials = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {credentials}"
            
        elif self.auth_method == AuthMethod.API_KEY:
            # API Key authentication
            if not self.api_key:
                raise ValueError("API key required for API key auth")
            headers["X-API-Key"] = self.api_key
            
        elif self.auth_method == AuthMethod.JWT:
            # JWT authentication
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
        # Default JWT expiry is 1 hour
        self.jwt_expiry = datetime.now() + timedelta(hours=1)
        
    def _is_jwt_expired(self) -> bool:
        """Check if JWT token is expired"""
        if not self.jwt_expiry:
            return True
        return datetime.now() >= self.jwt_expiry
    
    # Core API Methods
    
    async def get_system_status(self) -> Dict:
        """Get system status information"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/status/system",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    
    async def get_interfaces(self) -> List[Dict]:
        """Get all network interfaces"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/status/interface",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def get_interface(self, interface_id: str) -> Dict:
        """Get specific interface details"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/status/interface/{interface_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", {})
    
    # Firewall Rules Management
    
    async def get_firewall_rules(self, interface: Optional[str] = None) -> List[Dict]:
        """Get firewall rules, optionally filtered by interface"""
        headers = await self._get_auth_headers()
        params = {}
        if interface:
            params["interface"] = interface
            
        response = await self.client.get(
            f"{self.api_base}/firewall/rule",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def get_firewall_rule(self, rule_id: int) -> Dict:
        """Get specific firewall rule by ID"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/firewall/rule/{rule_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", {})
    
    async def create_firewall_rule(self, rule_data: Dict) -> Dict:
        """Create a new firewall rule"""
        headers = await self._get_auth_headers()
        response = await self.client.post(
            f"{self.api_base}/firewall/rule",
            headers=headers,
            json=rule_data
        )
        response.raise_for_status()
        return response.json()
    
    async def update_firewall_rule(self, rule_id: int, updates: Dict) -> Dict:
        """Update existing firewall rule"""
        headers = await self._get_auth_headers()
        response = await self.client.patch(
            f"{self.api_base}/firewall/rule/{rule_id}",
            headers=headers,
            json=updates
        )
        response.raise_for_status()
        return response.json()
    
    async def delete_firewall_rule(self, rule_id: int) -> Dict:
        """Delete firewall rule"""
        headers = await self._get_auth_headers()
        response = await self.client.delete(
            f"{self.api_base}/firewall/rule/{rule_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    
    async def apply_firewall_changes(self) -> Dict:
        """Apply pending firewall changes"""
        headers = await self._get_auth_headers()
        response = await self.client.post(
            f"{self.api_base}/firewall/apply",
            headers=headers,
            json={}
        )
        response.raise_for_status()
        return response.json()
    
    # NAT Rules
    
    async def get_nat_rules(self) -> List[Dict]:
        """Get NAT rules"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/firewall/nat/rule",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def create_nat_rule(self, rule_data: Dict) -> Dict:
        """Create NAT rule"""
        headers = await self._get_auth_headers()
        response = await self.client.post(
            f"{self.api_base}/firewall/nat/rule",
            headers=headers,
            json=rule_data
        )
        response.raise_for_status()
        return response.json()
    
    # Aliases
    
    async def get_aliases(self) -> List[Dict]:
        """Get all aliases"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/firewall/alias",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def create_alias(self, alias_data: Dict) -> Dict:
        """Create new alias"""
        headers = await self._get_auth_headers()
        response = await self.client.post(
            f"{self.api_base}/firewall/alias",
            headers=headers,
            json=alias_data
        )
        response.raise_for_status()
        return response.json()
    
    # Services
    
    async def get_services_status(self) -> List[Dict]:
        """Get status of all services"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/services",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def control_service(self, service_name: str, action: str) -> Dict:
        """Control a service (start, stop, restart)"""
        headers = await self._get_auth_headers()
        response = await self.client.post(
            f"{self.api_base}/services/{action}",
            headers=headers,
            json={"service": service_name}
        )
        response.raise_for_status()
        return response.json()
    
    # DHCP
    
    async def get_dhcp_leases(self) -> List[Dict]:
        """Get DHCP leases"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/services/dhcpd/lease",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def get_dhcp_static_mappings(self) -> List[Dict]:
        """Get DHCP static mappings"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/services/dhcpd/static_mapping",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    # VPN
    
    async def get_ipsec_status(self) -> Dict:
        """Get IPsec VPN status"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/status/ipsec",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", {})
    
    async def get_openvpn_status(self) -> List[Dict]:
        """Get OpenVPN status"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/status/openvpn",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    # System Logs
    
    async def get_system_logs(self, log_type: str = "system", lines: int = 50) -> List[str]:
        """Get system logs"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/diagnostics/log/{log_type}",
            headers=headers,
            params={"limit": lines}
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    # Diagnostics
    
    async def get_arp_table(self) -> List[Dict]:
        """Get ARP table"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/diagnostics/arp_table",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def get_routing_table(self) -> List[Dict]:
        """Get routing table"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/routing/static_route",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    # Configuration Management
    
    async def get_config_backup_list(self) -> List[Dict]:
        """Get list of configuration backups"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/system/config/backup",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def create_config_backup(self, description: str) -> Dict:
        """Create configuration backup"""
        headers = await self._get_auth_headers()
        response = await self.client.post(
            f"{self.api_base}/system/config/backup",
            headers=headers,
            json={"description": description}
        )
        response.raise_for_status()
        return response.json()
    
    # User Management
    
    async def get_users(self) -> List[Dict]:
        """Get all users"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/user",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", [])
    
    async def create_user(self, user_data: Dict) -> Dict:
        """Create new user"""
        headers = await self._get_auth_headers()
        response = await self.client.post(
            f"{self.api_base}/user",
            headers=headers,
            json=user_data
        )
        response.raise_for_status()
        return response.json()
    
    # API Settings
    
    async def get_api_settings(self) -> Dict:
        """Get REST API settings"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/system/restapi/settings",
            headers=headers
        )
        response.raise_for_status()
        return response.json().get("data", {})
    
    async def update_api_settings(self, settings: Dict) -> Dict:
        """Update REST API settings"""
        headers = await self._get_auth_headers()
        response = await self.client.patch(
            f"{self.api_base}/system/restapi/settings",
            headers=headers,
            json=settings
        )
        response.raise_for_status()
        return response.json()
    
    # OpenAPI Schema
    
    async def get_openapi_schema(self) -> Dict:
        """Get OpenAPI schema for the API"""
        headers = await self._get_auth_headers()
        response = await self.client.get(
            f"{self.api_base}/schema/openapi",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
    
    # Helper Methods
    
    async def test_connection(self) -> bool:
        """Test API connection"""
        try:
            await self.get_system_status()
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    
    async def test_api():
        # Initialize client with API key authentication
        client = PfSenseAPIv2Client(
            host="https://pfsense.example.com",
            auth_method=AuthMethod.API_KEY,
            api_key="your-api-key-here",
            verify_ssl=True,
            version=PfSenseVersion.CE_2_8_0
        )
        
        # Test connection
        if await client.test_connection():
            print("✓ Connected to pfSense API")
            
            # Get system status
            status = await client.get_system_status()
            print(f"System Status: {status}")
            
            # Get interfaces
            interfaces = await client.get_interfaces()
            print(f"Interfaces: {len(interfaces)} found")
            
            # Get firewall rules
            rules = await client.get_firewall_rules()
            print(f"Firewall Rules: {len(rules)} found")
        else:
            print("✗ Failed to connect to pfSense API")
        
        await client.close()
    
    # Run test
    # asyncio.run(test_api())