#!/usr/bin/env python3
"""
pfSense MCP Server - FastMCP Implementation
Focused on core functionality for pfSense CE and Plus editions
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

# FastMCP imports
from fastmcp import FastMCP

# Core imports for pfSense communication
import httpx
import paramiko
import xmltodict
from cachetools import TTLCache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Version
VERSION = "2.0.0"

# Initialize FastMCP server
mcp = FastMCP(
    "pfSense MCP Server",
    version=VERSION,
    description="Manage pfSense CE and Plus via Model Context Protocol"
)

# Connection Methods
class ConnectionMethod(str, Enum):
    REST = "rest"
    XMLRPC = "xmlrpc"
    SSH = "ssh"

# pfSense Connection Manager
class PfSenseConnectionManager:
    """Manages connections to pfSense CE and Plus editions"""
    
    def __init__(self):
        self.method = ConnectionMethod(os.getenv("PFSENSE_CONNECTION_METHOD", "rest"))
        self.base_url = os.getenv("PFSENSE_URL", "https://pfsense.local")
        self.verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
        self.timeout = int(os.getenv("CONNECTION_TIMEOUT", "30"))
        
        # Version detection
        self.pfsense_version = os.getenv("PFSENSE_VERSION", "ce")  # "ce" or "plus"
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            verify=self.verify_ssl,
            timeout=self.timeout
        )
        
        # Simple cache
        cache_ttl = int(os.getenv("CACHE_TTL", "300"))
        self.cache = TTLCache(maxsize=100, ttl=cache_ttl)
        
        logger.info(f"Connection manager initialized for pfSense {self.pfsense_version.upper()} using {self.method.value}")
    
    async def execute(self, command: str, params: Optional[Dict] = None) -> Any:
        """Execute command using configured method"""
        # Check cache for read operations
        if params is None:
            cache_key = f"{self.method}:{command}"
            if cache_key in self.cache:
                logger.debug(f"Cache hit for {command}")
                return self.cache[cache_key]
        
        try:
            if self.method == ConnectionMethod.REST:
                result = await self._execute_rest(command, params)
            elif self.method == ConnectionMethod.XMLRPC:
                result = await self._execute_xmlrpc(command, params)
            elif self.method == ConnectionMethod.SSH:
                result = await self._execute_ssh(command, params)
            else:
                raise ValueError(f"Unknown connection method: {self.method}")
            
            # Cache successful read operations
            if params is None:
                self.cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Command execution failed: {command} - {str(e)}")
            raise
    
    async def _execute_rest(self, command: str, params: Optional[Dict] = None) -> Any:
        """Execute via REST API - handles CE vs Plus differences"""
        api_key = os.getenv("PFSENSE_API_KEY")
        api_secret = os.getenv("PFSENSE_API_SECRET")
        
        # Version-specific authentication
        if self.pfsense_version == "plus":
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "X-API-Version": "2"
            }
            api_prefix = "/api/v2"
        else:  # CE version
            headers = {
                "Authorization": f"{api_key} {api_secret}",
                "Content-Type": "application/json"
            }
            api_prefix = "/api/v1"
        
        # Command to endpoint mapping
        endpoint_map = {
            "system.status": f"{api_prefix}/status/system",
            "firewall.rules.get": f"{api_prefix}/firewall/rules",
            "firewall.rule.create": f"{api_prefix}/firewall/rules",
            "firewall.apply": f"{api_prefix}/firewall/apply",
            "interface.list": f"{api_prefix}/interfaces",
            "interface.status": f"{api_prefix}/interfaces/status",
            "dhcp.leases": f"{api_prefix}/services/dhcp/leases",
            "arp.table": f"{api_prefix}/diagnostics/arp",
            "routing.table": f"{api_prefix}/diagnostics/routes",
            "logs.firewall": f"{api_prefix}/diagnostics/logs/firewall",
            "logs.system": f"{api_prefix}/diagnostics/logs/system",
            "services.status": f"{api_prefix}/services/status",
            "vpn.ipsec.status": f"{api_prefix}/vpn/ipsec/status",
            "vpn.openvpn.status": f"{api_prefix}/vpn/openvpn/status"
        }
        
        endpoint = endpoint_map.get(command)
        if not endpoint:
            # Dynamic endpoint construction
            endpoint = f"{api_prefix}/{command.replace('.', '/')}"
        
        url = f"{self.base_url}{endpoint}"
        
        if params:
            response = await self.http_client.post(url, headers=headers, json=params)
        else:
            response = await self.http_client.get(url, headers=headers)
        
        response.raise_for_status()
        return response.json()
    
    async def _execute_xmlrpc(self, command: str, params: Optional[Dict] = None) -> Any:
        """Execute via XML-RPC (legacy but still supported)"""
        username = os.getenv("PFSENSE_USERNAME")
        password = os.getenv("PFSENSE_PASSWORD")
        
        # Build XML-RPC request
        xml_request = f"""<?xml version='1.0'?>
        <methodCall>
            <methodName>{command}</methodName>
            <params>
                <param><value><string>{username}</string></value></param>
                <param><value><string>{password}</string></value></param>
        """
        
        if params:
            xml_request += f"<param><value>{xmltodict.unparse(params, full_document=False)}</value></param>"
        
        xml_request += "</params></methodCall>"
        
        response = await self.http_client.post(
            f"{self.base_url}/xmlrpc.php",
            content=xml_request,
            headers={"Content-Type": "text/xml"}
        )
        
        response.raise_for_status()
        result = xmltodict.parse(response.text)
        return result.get("methodResponse", {}).get("params", {}).get("param", {}).get("value", {})
    
    async def _execute_ssh(self, command: str, params: Optional[Dict] = None) -> Any:
        """Execute via SSH for advanced operations"""
        ssh_host = os.getenv("PFSENSE_SSH_HOST", self.base_url.replace("https://", "").replace("http://", ""))
        ssh_port = int(os.getenv("PFSENSE_SSH_PORT", "22"))
        ssh_user = os.getenv("PFSENSE_SSH_USERNAME")
        ssh_key = os.getenv("PFSENSE_SSH_KEY_PATH")
        
        # Map commands to shell commands
        shell_commands = {
            "system.status": "pfSsh.php playback getsystemstatus",
            "firewall.rules.get": "pfSsh.php playback listfirewallrules",
            "interface.list": "pfSsh.php playback listinterfaces",
            "service.restart": lambda p: f"pfSsh.php playback svc restart {p.get('service')}",
            "config.backup": "pfSsh.php playback backupconfig"
        }
        
        shell_cmd = shell_commands.get(command)
        if callable(shell_cmd):
            shell_cmd = shell_cmd(params or {})
        elif shell_cmd is None:
            raise ValueError(f"Unsupported SSH command: {command}")
        
        # Execute via SSH
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if ssh_key:
                client.connect(ssh_host, port=ssh_port, username=ssh_user, key_filename=ssh_key)
            else:
                client.connect(
                    ssh_host, 
                    port=ssh_port, 
                    username=ssh_user, 
                    password=os.getenv("PFSENSE_SSH_PASSWORD")
                )
            
            stdin, stdout, stderr = client.exec_command(shell_cmd)
            result = stdout.read().decode()
            error = stderr.read().decode()
            
            if error:
                logger.warning(f"SSH command stderr: {error}")
            
            # Parse result
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {"output": result, "error": error if error else None}
                
        finally:
            client.close()
    
    async def test_connection(self) -> bool:
        """Test connection to pfSense"""
        try:
            await self.execute("system.status")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    async def close(self):
        """Close connections"""
        await self.http_client.aclose()

# Global connection manager
connection_manager: Optional[PfSenseConnectionManager] = None

@mcp.context_manager
async def lifespan():
    """Application lifespan manager"""
    global connection_manager
    
    # Startup
    logger.info(f"Starting pfSense MCP Server v{VERSION}")
    connection_manager = PfSenseConnectionManager()
    
    # Test connection
    if await connection_manager.test_connection():
        logger.info("Successfully connected to pfSense")
    else:
        logger.warning("Could not connect to pfSense - check configuration")
    
    yield
    
    # Shutdown
    logger.info("Shutting down pfSense MCP Server")
    if connection_manager:
        await connection_manager.close()

# Resources - Direct access to pfSense data
@mcp.resource("pfsense://system/info")
async def get_system_info() -> str:
    """Get pfSense system information"""
    status = await connection_manager.execute("system.status")
    
    return json.dumps({
        "version": status.get("version", "unknown"),
        "platform": status.get("platform", "unknown"),
        "uptime": status.get("uptime", "unknown"),
        "cpu_usage": f"{status.get('cpu', 0)}%",
        "memory_usage": f"{status.get('mem', 0)}%",
        "disk_usage": f"{status.get('disk', 0)}%",
        "last_config_change": status.get("last_config_change", "unknown")
    }, indent=2)

@mcp.resource("pfsense://interfaces/all")
async def get_all_interfaces() -> str:
    """Get all network interfaces configuration"""
    interfaces = await connection_manager.execute("interface.list")
    return json.dumps(interfaces, indent=2)

@mcp.resource("pfsense://firewall/rules")
async def get_firewall_rules() -> str:
    """Get all firewall rules"""
    rules = await connection_manager.execute("firewall.rules.get")
    return json.dumps(rules, indent=2)

# Tools - Actions and queries

@mcp.tool()
async def system_status() -> Dict[str, Any]:
    """Get current pfSense system status"""
    status = await connection_manager.execute("system.status")
    
    return {
        "status": "online",
        "version": status.get("version", "unknown"),
        "uptime": status.get("uptime", "unknown"),
        "cpu_usage": status.get("cpu", 0),
        "memory_usage": status.get("mem", 0),
        "disk_usage": status.get("disk", 0),
        "temperature": status.get("temp", "N/A"),
        "last_check": datetime.utcnow().isoformat()
    }

@mcp.tool()
async def list_interfaces() -> List[Dict[str, Any]]:
    """List all network interfaces with their status"""
    interfaces = await connection_manager.execute("interface.list")
    
    return [
        {
            "name": iface.get("name"),
            "description": iface.get("descr", ""),
            "status": "up" if iface.get("enable") else "down",
            "ip_address": iface.get("ipaddr", "none"),
            "subnet": iface.get("subnet", ""),
            "gateway": iface.get("gateway", ""),
            "mtu": iface.get("mtu", 1500)
        }
        for iface in interfaces
    ]

@mcp.tool()
async def get_firewall_rules(
    interface: Optional[str] = None,
    disabled: bool = False
) -> List[Dict[str, Any]]:
    """
    Get firewall rules with optional filtering
    
    Args:
        interface: Filter by interface (wan, lan, etc)
        disabled: Include disabled rules
    """
    rules = await connection_manager.execute("firewall.rules.get")
    
    # Filter rules
    filtered_rules = []
    for rule in rules:
        # Skip disabled rules unless requested
        if not disabled and rule.get("disabled"):
            continue
        
        # Filter by interface if specified
        if interface and rule.get("interface") != interface:
            continue
        
        filtered_rules.append({
            "id": rule.get("tracker", rule.get("id")),
            "interface": rule.get("interface"),
            "type": rule.get("type", "pass"),
            "protocol": rule.get("protocol", "any"),
            "source": rule.get("source", {}),
            "destination": rule.get("destination", {}),
            "description": rule.get("descr", ""),
            "enabled": not rule.get("disabled", False)
        })
    
    return filtered_rules

@mcp.tool()
async def create_firewall_rule(
    interface: str,
    action: str,
    protocol: str = "any",
    source: str = "any",
    destination: str = "any",
    destination_port: Optional[str] = None,
    description: str = ""
) -> Dict[str, Any]:
    """
    Create a new firewall rule
    
    Args:
        interface: Interface to apply rule (wan, lan, etc)
        action: Rule action (pass, block, reject)
        protocol: Protocol (tcp, udp, icmp, any)
        source: Source address or 'any'
        destination: Destination address or 'any'
        destination_port: Destination port (optional)
        description: Rule description
    """
    rule = {
        "type": action,
        "interface": interface,
        "protocol": protocol,
        "descr": description or f"Created via MCP at {datetime.utcnow().isoformat()}"
    }
    
    # Handle source
    if source != "any":
        rule["source"] = {"address": source}
    
    # Handle destination
    if destination != "any":
        rule["destination"] = {"address": destination}
    
    if destination_port:
        rule["destination"]["port"] = destination_port
    
    # Create rule
    result = await connection_manager.execute("firewall.rule.create", rule)
    
    # Apply changes
    await connection_manager.execute("firewall.apply")
    
    return {
        "success": True,
        "rule_id": result.get("id"),
        "message": f"Firewall rule created on {interface}",
        "applied": True
    }

@mcp.tool()
async def block_ip_address(
    ip_address: str,
    reason: str = ""
) -> Dict[str, Any]:
    """
    Block an IP address by creating a block rule
    
    Args:
        ip_address: IP address to block
        reason: Reason for blocking (optional)
    """
    # Validate IP address format
    try:
        import ipaddress
        ipaddress.ip_address(ip_address)
    except ValueError:
        return {"success": False, "error": f"Invalid IP address: {ip_address}"}
    
    # Create block rule
    return await create_firewall_rule(
        interface="wan",
        action="block",
        source=ip_address,
        destination="any",
        description=f"Blocked: {reason}" if reason else f"Blocked IP: {ip_address}"
    )

@mcp.tool()
async def get_dhcp_leases() -> List[Dict[str, Any]]:
    """Get current DHCP leases"""
    leases = await connection_manager.execute("dhcp.leases")
    
    return [
        {
            "ip": lease.get("ip"),
            "mac": lease.get("mac"),
            "hostname": lease.get("hostname", "unknown"),
            "start": lease.get("start"),
            "end": lease.get("end"),
            "type": lease.get("type", "dynamic"),
            "online": lease.get("online", False)
        }
        for lease in leases
    ]

@mcp.tool()
async def get_arp_table() -> List[Dict[str, Any]]:
    """Get ARP table entries"""
    arp_entries = await connection_manager.execute("arp.table")
    
    return [
        {
            "ip": entry.get("ip"),
            "mac": entry.get("mac"),
            "interface": entry.get("interface"),
            "type": entry.get("type", "dynamic"),
            "expires": entry.get("expires")
        }
        for entry in arp_entries
    ]

@mcp.tool()
async def get_service_status(
    service: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get status of pfSense services
    
    Args:
        service: Specific service name (optional)
    """
    services = await connection_manager.execute("services.status")
    
    if service:
        # Return specific service status
        for svc in services:
            if svc.get("name") == service:
                return {
                    "name": svc.get("name"),
                    "description": svc.get("description"),
                    "status": svc.get("status"),
                    "enabled": svc.get("enabled", True)
                }
        return {"error": f"Service '{service}' not found"}
    
    # Return all services
    return {
        "services": [
            {
                "name": svc.get("name"),
                "description": svc.get("description"),
                "status": svc.get("status"),
                "enabled": svc.get("enabled", True)
            }
            for svc in services
        ]
    }

@mcp.tool()
async def restart_service(service: str) -> Dict[str, Any]:
    """
    Restart a pfSense service
    
    Args:
        service: Service name to restart
    """
    if connection_manager.method == ConnectionMethod.SSH:
        result = await connection_manager.execute("service.restart", {"service": service})
        return {
            "success": True,
            "service": service,
            "message": f"Service {service} restarted",
            "output": result.get("output", "")
        }
    else:
        # For REST/XML-RPC, use service control endpoint
        result = await connection_manager.execute(f"services.{service}.restart")
        return {
            "success": True,
            "service": service,
            "message": f"Service {service} restarted"
        }

@mcp.tool()
async def get_vpn_status(
    vpn_type: str = "all"
) -> Dict[str, Any]:
    """
    Get VPN status
    
    Args:
        vpn_type: Type of VPN (ipsec, openvpn, all)
    """
    status = {}
    
    if vpn_type in ["ipsec", "all"]:
        ipsec = await connection_manager.execute("vpn.ipsec.status")
        status["ipsec"] = {
            "enabled": ipsec.get("enable", False),
            "tunnels": len(ipsec.get("phase2", [])),
            "active_tunnels": sum(1 for t in ipsec.get("phase2", []) if t.get("connected"))
        }
    
    if vpn_type in ["openvpn", "all"]:
        openvpn = await connection_manager.execute("vpn.openvpn.status")
        status["openvpn"] = {
            "servers": len(openvpn.get("servers", [])),
            "clients": len(openvpn.get("clients", [])),
            "active_connections": openvpn.get("active_connections", 0)
        }
    
    return status

@mcp.tool()
async def backup_config() -> Dict[str, Any]:
    """Create a configuration backup"""
    if connection_manager.method == ConnectionMethod.SSH:
        result = await connection_manager.execute("config.backup")
        return {
            "success": True,
            "message": "Configuration backup created",
            "filename": result.get("filename", "config-backup.xml")
        }
    else:
        # For REST API, trigger backup
        result = await connection_manager.execute("system.backup.create")
        return {
            "success": True,
            "message": "Configuration backup created",
            "backup_id": result.get("id"),
            "timestamp": datetime.utcnow().isoformat()
        }

# Prompts for natural language interaction
@mcp.prompt()
async def firewall_assistant() -> str:
    """Assistant for firewall rule management"""
    return """You are a pfSense firewall assistant. You can help with:

1. Viewing existing firewall rules
2. Creating new firewall rules
3. Blocking specific IP addresses
4. Understanding firewall rule syntax

Available tools:
- get_firewall_rules: View current rules
- create_firewall_rule: Create new rules
- block_ip_address: Quick IP blocking

Always confirm actions before making changes and explain the impact of firewall rules."""

@mcp.prompt()
async def network_monitor() -> str:
    """Assistant for network monitoring"""
    return """You are a pfSense network monitoring assistant. You can help with:

1. Checking system status and health
2. Monitoring network interfaces
3. Viewing DHCP leases and ARP tables
4. Checking VPN connections
5. Service status monitoring

Available tools:
- system_status: Overall system health
- list_interfaces: Network interface status
- get_dhcp_leases: Active DHCP leases
- get_arp_table: ARP entries
- get_service_status: Service monitoring
- get_vpn_status: VPN connection status

Provide clear, concise information about network status."""

# Entry point
if __name__ == "__main__":
    import sys
    
    # Handle different run modes
    if "--help" in sys.argv:
        print(f"""
pfSense MCP Server v{VERSION}
FastMCP Implementation

Usage:
    python main_fastmcp.py [options]
    
Options:
    --stdio     Run in stdio mode for Claude Desktop
    --help      Show this help message
    
Environment Variables:
    PFSENSE_URL               pfSense URL (required)
    PFSENSE_VERSION          Version: ce or plus (default: ce)
    PFSENSE_CONNECTION_METHOD Connection method: rest, xmlrpc, ssh (default: rest)
    
    For REST API:
    PFSENSE_API_KEY          API key
    PFSENSE_API_SECRET       API secret (CE only)
    
    For XML-RPC:
    PFSENSE_USERNAME         Username
    PFSENSE_PASSWORD         Password
    
    For SSH:
    PFSENSE_SSH_HOST         SSH host
    PFSENSE_SSH_USERNAME     SSH username
    PFSENSE_SSH_KEY_PATH     Path to SSH private key
        """)
        sys.exit(0)
    
    # Run the server
    if "--stdio" in sys.argv:
        # stdio mode for Claude Desktop
        mcp.run(transport="stdio")
    else:
        # Default HTTP mode
        mcp.run()