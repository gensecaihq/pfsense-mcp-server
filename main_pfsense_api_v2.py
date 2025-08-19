#!/usr/bin/env python3
"""
pfSense MCP Server - Using pfSense REST API v2
Compatible with jaredhendrickson13/pfsense-api package
Supports pfSense CE 2.8.0 and pfSense Plus 24.11
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

# MCP imports
from fastmcp import FastMCP

# pfSense API v2 client
from pfsense_api_integration import (
    PfSenseAPIv2Client,
    AuthMethod,
    PfSenseVersion
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Version
VERSION = "3.0.0"

# Initialize FastMCP server
mcp = FastMCP(
    "pfSense MCP Server v3",
    version=VERSION,
    description="Production-ready pfSense management via REST API v2"
)

# Access levels
class AccessLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"

# Global API client
api_client: Optional[PfSenseAPIv2Client] = None

def get_api_client() -> PfSenseAPIv2Client:
    """Get or create API client"""
    global api_client
    if api_client is None:
        # Determine version
        pf_version = os.getenv("PFSENSE_VERSION", "CE_2_8_0")
        if pf_version == "PLUS_24_11":
            version = PfSenseVersion.PLUS_24_11
        else:
            version = PfSenseVersion.CE_2_8_0
        
        # Determine auth method
        auth_method_str = os.getenv("AUTH_METHOD", "api_key").lower()
        if auth_method_str == "basic":
            auth_method = AuthMethod.BASIC
        elif auth_method_str == "jwt":
            auth_method = AuthMethod.JWT
        else:
            auth_method = AuthMethod.API_KEY
        
        api_client = PfSenseAPIv2Client(
            host=os.getenv("PFSENSE_URL", "https://pfsense.local"),
            auth_method=auth_method,
            username=os.getenv("PFSENSE_USERNAME"),
            password=os.getenv("PFSENSE_PASSWORD"),
            api_key=os.getenv("PFSENSE_API_KEY"),
            verify_ssl=os.getenv("VERIFY_SSL", "true").lower() == "true",
            version=version
        )
        logger.info(f"API client initialized for pfSense {version.value} using {auth_method.value} auth")
    return api_client

# System Tools

@mcp.tool()
async def system_status() -> Dict:
    """Get current system status including CPU, memory, disk usage, and version info"""
    client = get_api_client()
    try:
        status = await client.get_system_status()
        return {
            "success": True,
            "data": status.get("data", status),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def list_interfaces() -> Dict:
    """List all network interfaces with their status and configuration"""
    client = get_api_client()
    try:
        interfaces = await client.get_interfaces()
        return {
            "success": True,
            "count": len(interfaces),
            "interfaces": interfaces,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list interfaces: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_interface_details(interface_id: str) -> Dict:
    """Get detailed information about a specific network interface
    
    Args:
        interface_id: Interface identifier (e.g., 'wan', 'lan', 'opt1')
    """
    client = get_api_client()
    try:
        interface = await client.get_interface(interface_id)
        return {
            "success": True,
            "interface": interface,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get interface {interface_id}: {e}")
        return {"success": False, "error": str(e)}

# Firewall Rules Tools

@mcp.tool()
async def list_firewall_rules(interface: Optional[str] = None) -> Dict:
    """List firewall rules, optionally filtered by interface
    
    Args:
        interface: Optional interface to filter rules (e.g., 'wan', 'lan')
    """
    client = get_api_client()
    try:
        rules = await client.get_firewall_rules(interface)
        return {
            "success": True,
            "count": len(rules),
            "interface": interface or "all",
            "rules": rules,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list firewall rules: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_firewall_rule(rule_id: int) -> Dict:
    """Get details of a specific firewall rule
    
    Args:
        rule_id: The ID of the firewall rule
    """
    client = get_api_client()
    try:
        rule = await client.get_firewall_rule(rule_id)
        return {
            "success": True,
            "rule": rule,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get firewall rule {rule_id}: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def create_firewall_rule(
    interface: str,
    type: str,
    protocol: str,
    source: str,
    destination: str,
    description: Optional[str] = None,
    destination_port: Optional[str] = None,
    log: bool = True
) -> Dict:
    """Create a new firewall rule
    
    Args:
        interface: Interface for the rule (e.g., 'wan', 'lan')
        type: Rule type ('pass', 'block', 'reject')
        protocol: Protocol ('tcp', 'udp', 'icmp', 'any')
        source: Source address ('any' or specific IP/network)
        destination: Destination address ('any' or specific IP/network)
        description: Optional rule description
        destination_port: Optional destination port or range
        log: Whether to log matches (default: True)
    """
    client = get_api_client()
    
    rule_data = {
        "interface": interface,
        "type": type,
        "ipprotocol": "inet",
        "protocol": protocol,
        "source": source,
        "destination": destination,
        "descr": description or f"Created via MCP at {datetime.utcnow().isoformat()}",
        "log": log
    }
    
    if destination_port:
        rule_data["destination_port"] = destination_port
    
    try:
        result = await client.create_firewall_rule(rule_data)
        # Apply changes
        await client.apply_firewall_changes()
        return {
            "success": True,
            "message": "Firewall rule created and applied",
            "rule": result.get("data", result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create firewall rule: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def update_firewall_rule(
    rule_id: int,
    updates: Dict
) -> Dict:
    """Update an existing firewall rule
    
    Args:
        rule_id: The ID of the rule to update
        updates: Dictionary of fields to update
    """
    client = get_api_client()
    try:
        result = await client.update_firewall_rule(rule_id, updates)
        # Apply changes
        await client.apply_firewall_changes()
        return {
            "success": True,
            "message": "Firewall rule updated and applied",
            "rule": result.get("data", result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update firewall rule {rule_id}: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def delete_firewall_rule(rule_id: int) -> Dict:
    """Delete a firewall rule
    
    Args:
        rule_id: The ID of the rule to delete
    """
    client = get_api_client()
    try:
        await client.delete_firewall_rule(rule_id)
        # Apply changes
        await client.apply_firewall_changes()
        return {
            "success": True,
            "message": f"Firewall rule {rule_id} deleted and changes applied",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to delete firewall rule {rule_id}: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def block_ip_address(
    ip_address: str,
    description: Optional[str] = None,
    interface: str = "wan"
) -> Dict:
    """Block an IP address by creating a firewall rule
    
    Args:
        ip_address: IP address to block
        description: Optional description for the block rule
        interface: Interface to apply the block (default: 'wan')
    """
    return await create_firewall_rule(
        interface=interface,
        type="block",
        protocol="any",
        source=ip_address,
        destination="any",
        description=description or f"Blocked {ip_address} via MCP",
        log=True
    )

# NAT Tools

@mcp.tool()
async def list_nat_rules() -> Dict:
    """List all NAT rules"""
    client = get_api_client()
    try:
        rules = await client.get_nat_rules()
        return {
            "success": True,
            "count": len(rules),
            "rules": rules,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list NAT rules: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def create_port_forward(
    interface: str,
    protocol: str,
    external_port: str,
    internal_ip: str,
    internal_port: str,
    description: Optional[str] = None
) -> Dict:
    """Create a port forwarding rule
    
    Args:
        interface: External interface (e.g., 'wan')
        protocol: Protocol ('tcp', 'udp', or 'tcp/udp')
        external_port: External port or range
        internal_ip: Internal IP address
        internal_port: Internal port or range
        description: Optional description
    """
    client = get_api_client()
    
    nat_data = {
        "interface": interface,
        "protocol": protocol,
        "target": internal_ip,
        "local-port": internal_port,
        "destination": {
            "port": external_port
        },
        "descr": description or f"Port forward created via MCP"
    }
    
    try:
        result = await client.create_nat_rule(nat_data)
        return {
            "success": True,
            "message": "Port forward created",
            "rule": result.get("data", result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create port forward: {e}")
        return {"success": False, "error": str(e)}

# Alias Tools

@mcp.tool()
async def list_aliases() -> Dict:
    """List all configured aliases"""
    client = get_api_client()
    try:
        aliases = await client.get_aliases()
        return {
            "success": True,
            "count": len(aliases),
            "aliases": aliases,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list aliases: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def create_alias(
    name: str,
    type: str,
    addresses: List[str],
    description: Optional[str] = None
) -> Dict:
    """Create a new alias
    
    Args:
        name: Alias name
        type: Alias type ('host', 'network', 'port', 'url')
        addresses: List of addresses/values for the alias
        description: Optional description
    """
    client = get_api_client()
    
    alias_data = {
        "name": name,
        "type": type,
        "address": addresses,
        "descr": description or f"Created via MCP"
    }
    
    try:
        result = await client.create_alias(alias_data)
        return {
            "success": True,
            "message": f"Alias '{name}' created",
            "alias": result.get("data", result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create alias: {e}")
        return {"success": False, "error": str(e)}

# Service Tools

@mcp.tool()
async def list_services() -> Dict:
    """List all services and their status"""
    client = get_api_client()
    try:
        services = await client.get_services_status()
        return {
            "success": True,
            "count": len(services),
            "services": services,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list services: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def restart_service(service_name: str) -> Dict:
    """Restart a service
    
    Args:
        service_name: Name of the service to restart
    """
    client = get_api_client()
    try:
        result = await client.control_service(service_name, "restart")
        return {
            "success": True,
            "message": f"Service '{service_name}' restarted",
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to restart service {service_name}: {e}")
        return {"success": False, "error": str(e)}

# DHCP Tools

@mcp.tool()
async def list_dhcp_leases() -> Dict:
    """List current DHCP leases"""
    client = get_api_client()
    try:
        leases = await client.get_dhcp_leases()
        return {
            "success": True,
            "count": len(leases),
            "leases": leases,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list DHCP leases: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def list_dhcp_static_mappings() -> Dict:
    """List DHCP static mappings"""
    client = get_api_client()
    try:
        mappings = await client.get_dhcp_static_mappings()
        return {
            "success": True,
            "count": len(mappings),
            "mappings": mappings,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list DHCP static mappings: {e}")
        return {"success": False, "error": str(e)}

# VPN Tools

@mcp.tool()
async def get_ipsec_status() -> Dict:
    """Get IPsec VPN status"""
    client = get_api_client()
    try:
        status = await client.get_ipsec_status()
        return {
            "success": True,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get IPsec status: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_openvpn_status() -> Dict:
    """Get OpenVPN status"""
    client = get_api_client()
    try:
        status = await client.get_openvpn_status()
        return {
            "success": True,
            "servers": status,
            "count": len(status),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get OpenVPN status: {e}")
        return {"success": False, "error": str(e)}

# Log Tools

@mcp.tool()
async def get_firewall_logs(lines: int = 50) -> Dict:
    """Get recent firewall logs
    
    Args:
        lines: Number of log lines to retrieve (default: 50)
    """
    client = get_api_client()
    try:
        logs = await client.get_system_logs("firewall", lines)
        return {
            "success": True,
            "count": len(logs),
            "logs": logs,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get firewall logs: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_system_logs(lines: int = 50) -> Dict:
    """Get recent system logs
    
    Args:
        lines: Number of log lines to retrieve (default: 50)
    """
    client = get_api_client()
    try:
        logs = await client.get_system_logs("system", lines)
        return {
            "success": True,
            "count": len(logs),
            "logs": logs,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system logs: {e}")
        return {"success": False, "error": str(e)}

# Diagnostic Tools

@mcp.tool()
async def get_arp_table() -> Dict:
    """Get the ARP table"""
    client = get_api_client()
    try:
        arp = await client.get_arp_table()
        return {
            "success": True,
            "count": len(arp),
            "entries": arp,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get ARP table: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def get_routing_table() -> Dict:
    """Get the routing table"""
    client = get_api_client()
    try:
        routes = await client.get_routing_table()
        return {
            "success": True,
            "count": len(routes),
            "routes": routes,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get routing table: {e}")
        return {"success": False, "error": str(e)}

# Configuration Tools

@mcp.tool()
async def list_config_backups() -> Dict:
    """List available configuration backups"""
    client = get_api_client()
    try:
        backups = await client.get_config_backup_list()
        return {
            "success": True,
            "count": len(backups),
            "backups": backups,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list config backups: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def create_config_backup(description: str) -> Dict:
    """Create a configuration backup
    
    Args:
        description: Description for the backup
    """
    client = get_api_client()
    try:
        result = await client.create_config_backup(description)
        return {
            "success": True,
            "message": "Configuration backup created",
            "backup": result.get("data", result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create config backup: {e}")
        return {"success": False, "error": str(e)}

# User Management Tools

@mcp.tool()
async def list_users() -> Dict:
    """List all users"""
    client = get_api_client()
    try:
        users = await client.get_users()
        return {
            "success": True,
            "count": len(users),
            "users": users,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        return {"success": False, "error": str(e)}

# Connection Test Tool

@mcp.tool()
async def test_connection() -> Dict:
    """Test connection to pfSense API"""
    client = get_api_client()
    try:
        connected = await client.test_connection()
        if connected:
            return {
                "success": True,
                "message": "Successfully connected to pfSense API",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "success": False,
                "message": "Failed to connect to pfSense API",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# API Info Tool

@mcp.tool()
async def get_api_info() -> Dict:
    """Get information about the REST API configuration"""
    client = get_api_client()
    try:
        settings = await client.get_api_settings()
        return {
            "success": True,
            "settings": settings,
            "version": "v2",
            "package": "jaredhendrickson13/pfsense-api",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get API info: {e}")
        return {"success": False, "error": str(e)}

# Main execution
if __name__ == "__main__":
    import uvicorn
    
    # Run the FastMCP server
    uvicorn.run(
        "main_pfsense_api_v2:mcp",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8000")),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )