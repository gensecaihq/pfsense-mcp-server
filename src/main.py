#!/usr/bin/env python3
"""
Enhanced pfSense MCP Server with Advanced API Features
Implements: Object IDs, Queries/Filters, HATEOAS, Control Parameters
Compatible with pfSense REST API v2 (jaredhendrickson13/pfsense-api)
"""

import os
import sys
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

# MCP imports
from fastmcp import FastMCP

# Enhanced pfSense API client
from .pfsense_api_enhanced import (
    EnhancedPfSenseAPIClient,
    AuthMethod,
    PfSenseVersion,
    QueryFilter,
    SortOptions,
    PaginationOptions,
    ControlParameters,
    create_ip_filter,
    create_port_filter,
    create_interface_filter,
    create_pagination,
    create_default_sort
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Version
VERSION = "4.0.0"

# Initialize FastMCP server
mcp = FastMCP(
    "pfSense Enhanced MCP Server",
    version=VERSION,
    description="Advanced pfSense management with filtering, sorting, and HATEOAS support"
)

# Global API client
api_client: Optional[EnhancedPfSenseAPIClient] = None

def get_api_client() -> EnhancedPfSenseAPIClient:
    """Get or create enhanced API client"""
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
        
        api_client = EnhancedPfSenseAPIClient(
            host=os.getenv("PFSENSE_URL", "https://pfsense.local"),
            auth_method=auth_method,
            username=os.getenv("PFSENSE_USERNAME"),
            password=os.getenv("PFSENSE_PASSWORD"),
            api_key=os.getenv("PFSENSE_API_KEY"),
            verify_ssl=os.getenv("VERIFY_SSL", "true").lower() == "true",
            version=version,
            enable_hateoas=os.getenv("ENABLE_HATEOAS", "false").lower() == "true"
        )
        logger.info(f"Enhanced API client initialized for pfSense {version.value}")
    return api_client

# Enhanced System Tools

@mcp.tool()
async def system_status() -> Dict:
    """Get current system status including CPU, memory, disk usage, and version info"""
    client = get_api_client()
    try:
        status = await client.get_system_status()
        
        # Extract HATEOAS links if available
        links = client.extract_links(status)
        
        return {
            "success": True,
            "data": status.get("data", status),
            "links": links,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def search_interfaces(
    search_term: Optional[str] = None,
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name"
) -> Dict:
    """Search and filter network interfaces with advanced options
    
    Args:
        search_term: Search in interface names/descriptions
        status_filter: Filter by status (up, down, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (name, status, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        
        if search_term:
            filters.append(QueryFilter("name", search_term, "contains"))
        
        if status_filter:
            filters.append(QueryFilter("status", status_filter))
        
        pagination = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)
        
        interfaces = await client.get_interfaces(
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )
        
        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "total_results": len(interfaces.get("data", [])),
            "interfaces": interfaces.get("data", []),
            "links": client.extract_links(interfaces),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search interfaces: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def find_interfaces_by_status(status: str) -> Dict:
    """Find interfaces by their current status
    
    Args:
        status: Interface status to filter by (up, down, etc.)
    """
    client = get_api_client()
    try:
        interfaces = await client.find_interfaces_by_status(status)
        
        return {
            "success": True,
            "status_filter": status,
            "count": len(interfaces.get("data", [])),
            "interfaces": interfaces.get("data", []),
            "links": client.extract_links(interfaces),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to find interfaces by status: {e}")
        return {"success": False, "error": str(e)}

# Enhanced Firewall Tools

@mcp.tool()
async def search_firewall_rules(
    interface: Optional[str] = None,
    source_ip: Optional[str] = None,
    destination_port: Optional[Union[int, str]] = None,
    rule_type: Optional[str] = None,
    search_description: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "sequence"
) -> Dict:
    """Search firewall rules with advanced filtering and pagination
    
    Args:
        interface: Filter by interface (wan, lan, etc.)
        source_ip: Filter by source IP (supports partial matching)
        destination_port: Filter by destination port
        rule_type: Filter by rule type (pass, block, reject)
        search_description: Search in rule descriptions
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by (sequence, interface, type, etc.)
    """
    client = get_api_client()
    try:
        filters = []
        
        if interface:
            filters.append(create_interface_filter(interface))
        
        if source_ip:
            filters.append(QueryFilter("source", source_ip, "contains"))
        
        if destination_port:
            filters.append(create_port_filter(destination_port))
        
        if rule_type:
            filters.append(QueryFilter("type", rule_type))
        
        if search_description:
            filters.append(QueryFilter("descr", search_description, "contains"))
        
        pagination = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)
        
        rules = await client.get_firewall_rules(
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )
        
        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "interface": interface,
                "source_ip": source_ip,
                "destination_port": destination_port,
                "rule_type": rule_type,
                "search_description": search_description
            },
            "count": len(rules.get("data", [])),
            "rules": rules.get("data", []),
            "links": client.extract_links(rules),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search firewall rules: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def find_blocked_rules(
    interface: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict:
    """Find all firewall rules that block or reject traffic
    
    Args:
        interface: Optional interface filter
        page: Page number for pagination
        page_size: Number of results per page
    """
    client = get_api_client()
    try:
        pagination = create_pagination(page, page_size)
        sort = create_default_sort("sequence")
        
        rules = await client.find_blocked_rules()
        
        # Apply interface filter if specified
        if interface:
            filtered_rules = []
            for rule in rules.get("data", []):
                if rule.get("interface") == interface:
                    filtered_rules.append(rule)
            rules["data"] = filtered_rules
        
        return {
            "success": True,
            "interface_filter": interface,
            "count": len(rules.get("data", [])),
            "blocked_rules": rules.get("data", []),
            "links": client.extract_links(rules),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to find blocked rules: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def create_firewall_rule_advanced(
    interface: str,
    rule_type: str,
    protocol: str,
    source: str,
    destination: str,
    description: Optional[str] = None,
    destination_port: Optional[str] = None,
    position: Optional[int] = None,
    apply_immediately: bool = True,
    log_matches: bool = True
) -> Dict:
    """Create a firewall rule with advanced placement and control options
    
    Args:
        interface: Interface for the rule (wan, lan, etc.)
        rule_type: Rule type (pass, block, reject)
        protocol: Protocol (tcp, udp, icmp, any)
        source: Source address (any, IP, network, alias)
        destination: Destination address (any, IP, network, alias)
        description: Optional rule description
        destination_port: Optional destination port or range
        position: Optional position to insert rule (0 = top)
        apply_immediately: Whether to apply changes immediately
        log_matches: Whether to log rule matches
    """
    client = get_api_client()
    
    rule_data = {
        "interface": interface,
        "type": rule_type,
        "ipprotocol": "inet",
        "protocol": protocol,
        "source": source,
        "destination": destination,
        "descr": description or f"Created via Enhanced MCP at {datetime.utcnow().isoformat()}",
        "log": log_matches
    }
    
    if destination_port:
        rule_data["destination_port"] = destination_port
    
    # Set control parameters
    control = ControlParameters(
        apply=apply_immediately,
        placement=position
    )
    
    try:
        result = await client.create_firewall_rule(rule_data, control)
        
        return {
            "success": True,
            "message": "Firewall rule created with advanced options",
            "rule": result.get("data", result),
            "applied_immediately": apply_immediately,
            "position": position,
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to create advanced firewall rule: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def move_firewall_rule(
    rule_id: int,
    new_position: int,
    apply_immediately: bool = True
) -> Dict:
    """Move a firewall rule to a new position in the rule order
    
    Args:
        rule_id: ID of the rule to move
        new_position: New position (0 = top, higher numbers = lower priority)
        apply_immediately: Whether to apply changes immediately
    """
    client = get_api_client()
    try:
        result = await client.move_firewall_rule(
            rule_id, new_position, apply_immediately
        )
        
        return {
            "success": True,
            "message": f"Rule {rule_id} moved to position {new_position}",
            "rule_id": rule_id,
            "new_position": new_position,
            "applied": apply_immediately,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to move firewall rule: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def bulk_block_ips(
    ip_addresses: List[str],
    interface: str = "wan",
    description_prefix: str = "Bulk block via MCP"
) -> Dict:
    """Block multiple IP addresses at once
    
    Args:
        ip_addresses: List of IP addresses to block
        interface: Interface to apply blocks on
        description_prefix: Prefix for rule descriptions
    """
    client = get_api_client()
    results = []
    errors = []
    
    for ip in ip_addresses:
        try:
            rule_data = {
                "interface": interface,
                "type": "block",
                "ipprotocol": "inet",
                "protocol": "any",
                "source": ip,
                "destination": "any",
                "descr": f"{description_prefix}: {ip}",
                "log": True
            }
            
            # Don't apply immediately for bulk operations
            control = ControlParameters(apply=False)
            result = await client.create_firewall_rule(rule_data, control)
            results.append({"ip": ip, "success": True, "rule_id": result.get("data", {}).get("id")})
            
        except Exception as e:
            logger.error(f"Failed to block IP {ip}: {e}")
            errors.append({"ip": ip, "error": str(e)})
    
    # Apply all changes at once
    if results:
        try:
            await client._make_request("POST", "/firewall/apply")
            applied = True
        except Exception as e:
            applied = False
            logger.error(f"Failed to apply bulk changes: {e}")
    else:
        applied = False
    
    return {
        "success": len(results) > 0,
        "total_requested": len(ip_addresses),
        "successful": len(results),
        "failed": len(errors),
        "applied": applied,
        "results": results,
        "errors": errors,
        "timestamp": datetime.utcnow().isoformat()
    }

# Enhanced Alias Tools

@mcp.tool()
async def search_aliases(
    search_term: Optional[str] = None,
    alias_type: Optional[str] = None,
    containing_ip: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "name"
) -> Dict:
    """Search aliases with advanced filtering options
    
    Args:
        search_term: Search in alias names or descriptions
        alias_type: Filter by alias type (host, network, port, url)
        containing_ip: Find aliases containing this IP address
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by
    """
    client = get_api_client()
    try:
        filters = []
        
        if search_term:
            filters.append(QueryFilter("name", search_term, "contains"))
        
        if alias_type:
            filters.append(QueryFilter("type", alias_type))
        
        if containing_ip:
            filters.append(QueryFilter("address", containing_ip, "contains"))
        
        pagination = create_pagination(page, page_size)
        sort = create_default_sort(sort_by)
        
        aliases = await client.get_aliases(
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )
        
        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "alias_type": alias_type,
                "containing_ip": containing_ip
            },
            "count": len(aliases.get("data", [])),
            "aliases": aliases.get("data", []),
            "links": client.extract_links(aliases),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search aliases: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def manage_alias_addresses(
    alias_id: int,
    action: str,
    addresses: List[str]
) -> Dict:
    """Add or remove addresses from an existing alias
    
    Args:
        alias_id: ID of the alias to modify
        action: Action to perform ('add' or 'remove')
        addresses: List of addresses to add or remove
    """
    client = get_api_client()
    try:
        if action.lower() == "add":
            result = await client.add_to_alias(alias_id, addresses)
            message = f"Added {len(addresses)} addresses to alias {alias_id}"
        elif action.lower() == "remove":
            result = await client.remove_from_alias(alias_id, addresses)
            message = f"Removed {len(addresses)} addresses from alias {alias_id}"
        else:
            return {"success": False, "error": "Action must be 'add' or 'remove'"}
        
        return {
            "success": True,
            "message": message,
            "alias_id": alias_id,
            "action": action,
            "addresses": addresses,
            "result": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to manage alias addresses: {e}")
        return {"success": False, "error": str(e)}

# Enhanced Log Analysis Tools

@mcp.tool()
async def analyze_blocked_traffic(
    hours_back: int = 24,
    limit: int = 100,
    group_by_source: bool = True
) -> Dict:
    """Analyze blocked traffic patterns from firewall logs
    
    Args:
        hours_back: How many hours back to analyze
        limit: Maximum number of log entries to analyze
        group_by_source: Whether to group results by source IP
    """
    client = get_api_client()
    try:
        # Get blocked traffic logs
        sort = create_default_sort("timestamp", descending=True)
        logs = await client.get_blocked_traffic_logs(lines=limit)
        
        log_data = logs.get("data", [])
        
        if group_by_source:
            # Group by source IP
            source_stats = {}
            for entry in log_data:
                src_ip = entry.get("src_ip", "unknown")
                if src_ip not in source_stats:
                    source_stats[src_ip] = {
                        "count": 0,
                        "ports": set(),
                        "destinations": set(),
                        "latest_time": None
                    }
                
                source_stats[src_ip]["count"] += 1
                
                if entry.get("dst_port"):
                    source_stats[src_ip]["ports"].add(entry["dst_port"])
                
                if entry.get("dst_ip"):
                    source_stats[src_ip]["destinations"].add(entry["dst_ip"])
                
                if entry.get("timestamp"):
                    source_stats[src_ip]["latest_time"] = entry["timestamp"]
            
            # Convert sets to lists for JSON serialization
            for ip, stats in source_stats.items():
                stats["ports"] = list(stats["ports"])
                stats["destinations"] = list(stats["destinations"])
                stats["threat_score"] = min(10, stats["count"] / 10)
            
            # Sort by count
            sorted_sources = sorted(
                source_stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )
            
            analysis = {
                "grouped_by": "source_ip",
                "total_unique_sources": len(source_stats),
                "top_sources": dict(sorted_sources[:20])
            }
        else:
            analysis = {
                "grouped_by": "none",
                "raw_entries": log_data
            }
        
        return {
            "success": True,
            "analysis_period_hours": hours_back,
            "total_entries_analyzed": len(log_data),
            "analysis": analysis,
            "links": client.extract_links(logs),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to analyze blocked traffic: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def search_logs_by_ip(
    ip_address: str,
    log_type: str = "firewall",
    lines: int = 100,
    include_related: bool = True
) -> Dict:
    """Search logs for activity related to a specific IP address
    
    Args:
        ip_address: IP address to search for
        log_type: Type of logs to search (firewall, system, etc.)
        lines: Number of log lines to retrieve
        include_related: Whether to include related traffic (src and dst)
    """
    client = get_api_client()
    try:
        if log_type == "firewall":
            logs = await client.get_logs_by_ip(ip_address, lines)
        else:
            # For other log types, use general log search
            filters = [QueryFilter("message", ip_address, "contains")]
            logs = await client._make_request(
                "GET", f"/diagnostics/log/{log_type}",
                filters=filters,
                pagination=PaginationOptions(limit=lines)
            )
        
        log_entries = logs.get("data", [])
        
        # Analyze patterns if firewall logs
        if log_type == "firewall" and log_entries:
            patterns = {
                "total_entries": len(log_entries),
                "blocked_count": 0,
                "allowed_count": 0,
                "ports_accessed": set(),
                "protocols_used": set()
            }
            
            for entry in log_entries:
                action = entry.get("action", "").lower()
                if "block" in action or "reject" in action:
                    patterns["blocked_count"] += 1
                elif "pass" in action or "allow" in action:
                    patterns["allowed_count"] += 1
                
                if entry.get("dst_port"):
                    patterns["ports_accessed"].add(entry["dst_port"])
                
                if entry.get("protocol"):
                    patterns["protocols_used"].add(entry["protocol"])
            
            # Convert sets to lists
            patterns["ports_accessed"] = list(patterns["ports_accessed"])
            patterns["protocols_used"] = list(patterns["protocols_used"])
        else:
            patterns = None
        
        return {
            "success": True,
            "ip_address": ip_address,
            "log_type": log_type,
            "total_entries": len(log_entries),
            "patterns": patterns,
            "log_entries": log_entries,
            "links": client.extract_links(logs),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search logs by IP: {e}")
        return {"success": False, "error": str(e)}

# Enhanced DHCP Tools

@mcp.tool()
async def search_dhcp_leases(
    search_term: Optional[str] = None,
    interface: Optional[str] = None,
    mac_address: Optional[str] = None,
    hostname: Optional[str] = None,
    state: str = "active",
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "start"
) -> Dict:
    """Search DHCP leases with advanced filtering
    
    Args:
        search_term: General search term for hostname or IP
        interface: Filter by interface
        mac_address: Filter by specific MAC address
        hostname: Filter by hostname (supports partial matching)
        state: Filter by lease state (active, expired, etc.)
        page: Page number for pagination
        page_size: Number of results per page
        sort_by: Field to sort by
    """
    client = get_api_client()
    try:
        filters = []
        
        if search_term:
            filters.append(QueryFilter("hostname", search_term, "contains"))
        
        if interface:
            filters.append(create_interface_filter(interface))
        
        if mac_address:
            filters.append(QueryFilter("mac", mac_address))
        
        if hostname:
            filters.append(QueryFilter("hostname", hostname, "contains"))
        
        if state:
            filters.append(QueryFilter("state", state))
        
        pagination = create_pagination(page, page_size)
        sort = create_default_sort(sort_by, descending=True)
        
        leases = await client.get_dhcp_leases(
            interface=interface,
            filters=filters if filters else None,
            sort=sort,
            pagination=pagination
        )
        
        return {
            "success": True,
            "page": page,
            "page_size": page_size,
            "filters_applied": {
                "search_term": search_term,
                "interface": interface,
                "mac_address": mac_address,
                "hostname": hostname,
                "state": state
            },
            "count": len(leases.get("data", [])),
            "leases": leases.get("data", []),
            "links": client.extract_links(leases),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to search DHCP leases: {e}")
        return {"success": False, "error": str(e)}

# HATEOAS Navigation Tools

@mcp.tool()
async def follow_api_link(link_url: str) -> Dict:
    """Follow a HATEOAS link from a previous API response
    
    Args:
        link_url: The link URL to follow (from _links section)
    """
    client = get_api_client()
    try:
        result = await client.follow_link(link_url)
        
        return {
            "success": True,
            "followed_link": link_url,
            "data": result.get("data", result),
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to follow link: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def enable_hateoas() -> Dict:
    """Enable HATEOAS links in API responses for this session"""
    client = get_api_client()
    result = await client.enable_hateoas()
    return {
        "success": True,
        "message": "HATEOAS enabled - API responses will now include navigation links",
        "result": result,
        "timestamp": datetime.utcnow().isoformat()
    }

@mcp.tool()
async def disable_hateoas() -> Dict:
    """Disable HATEOAS links in API responses for this session"""
    client = get_api_client()
    result = await client.disable_hateoas()
    return {
        "success": True,
        "message": "HATEOAS disabled - API responses will be more compact",
        "result": result,
        "timestamp": datetime.utcnow().isoformat()
    }

# Object ID Management Tools

@mcp.tool()
async def refresh_object_ids(endpoint: str) -> Dict:
    """Refresh object IDs by re-querying an endpoint (handles ID changes after deletions)
    
    Args:
        endpoint: API endpoint to refresh (e.g., '/firewall/rule')
    """
    client = get_api_client()
    try:
        result = await client.refresh_object_ids(endpoint)
        
        return {
            "success": True,
            "endpoint": endpoint,
            "refreshed_count": len(result.get("data", [])),
            "objects": result.get("data", []),
            "message": "Object IDs refreshed - use updated IDs for future operations",
            "links": client.extract_links(result),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to refresh object IDs: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def find_object_by_field(
    endpoint: str,
    field: str,
    value: str
) -> Dict:
    """Find an object by a specific field value (safer than using IDs)
    
    Args:
        endpoint: API endpoint to search
        field: Field name to search by
        value: Value to search for
    """
    client = get_api_client()
    try:
        obj = await client.find_object_by_field(endpoint, field, value)
        
        if obj:
            return {
                "success": True,
                "endpoint": endpoint,
                "search_field": field,
                "search_value": value,
                "found": True,
                "object": obj,
                "object_id": obj.get("id"),
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "success": True,
                "endpoint": endpoint,
                "search_field": field,
                "search_value": value,
                "found": False,
                "message": "No object found matching criteria",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Failed to find object by field: {e}")
        return {"success": False, "error": str(e)}

# API Capabilities and Testing

@mcp.tool()
async def get_api_capabilities() -> Dict:
    """Get comprehensive API capabilities and configuration"""
    client = get_api_client()
    try:
        capabilities = await client.get_api_capabilities()
        
        return {
            "success": True,
            "api_version": "v2",
            "package": "jaredhendrickson13/pfsense-api",
            "pfsense_version": os.getenv("PFSENSE_VERSION", "CE_2_8_0"),
            "capabilities": capabilities.get("data", capabilities),
            "features": {
                "object_ids": "Dynamic, non-persistent",
                "queries_filters": "Full support with multiple operators",
                "sorting": "Multi-field sorting supported",
                "pagination": "Limit/offset based",
                "hateoas": f"{'Enabled' if client.enable_hateoas else 'Disabled'}",
                "control_parameters": "Apply, async, placement, append, remove"
            },
            "links": client.extract_links(capabilities),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get API capabilities: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
async def test_enhanced_connection() -> Dict:
    """Test enhanced API connection with feature validation"""
    client = get_api_client()
    try:
        # Test basic connection
        connected = await client.test_connection()
        
        if not connected:
            return {
                "success": False,
                "message": "Basic connection failed",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Test advanced features
        tests = []
        
        # Test filtering
        try:
            await client.get_interfaces(
                filters=[QueryFilter("status", "up")],
                pagination=PaginationOptions(limit=1)
            )
            tests.append({"feature": "filtering", "status": "working"})
        except Exception as e:
            tests.append({"feature": "filtering", "status": "failed", "error": str(e)})
        
        # Test sorting
        try:
            await client.get_firewall_rules(
                sort=SortOptions(sort_by="interface"),
                pagination=PaginationOptions(limit=1)
            )
            tests.append({"feature": "sorting", "status": "working"})
        except Exception as e:
            tests.append({"feature": "sorting", "status": "failed", "error": str(e)})
        
        # Test HATEOAS if enabled
        if client.enable_hateoas:
            try:
                result = await client.get_system_status()
                links = client.extract_links(result)
                if links:
                    tests.append({"feature": "hateoas", "status": "working", "links_found": len(links)})
                else:
                    tests.append({"feature": "hateoas", "status": "no_links"})
            except Exception as e:
                tests.append({"feature": "hateoas", "status": "failed", "error": str(e)})
        
        working_features = len([t for t in tests if t["status"] == "working"])
        
        return {
            "success": True,
            "message": f"Enhanced connection test completed - {working_features}/{len(tests)} features working",
            "basic_connection": True,
            "feature_tests": tests,
            "hateoas_enabled": client.enable_hateoas,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Enhanced connection test failed: {e}")
        return {"success": False, "error": str(e)}

# Main execution
if __name__ == "__main__":
    import uvicorn
    
    # Run the Enhanced FastMCP server
    uvicorn.run(
        "main_enhanced_mcp:mcp",
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8000")),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )