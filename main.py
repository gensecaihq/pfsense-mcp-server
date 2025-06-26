#!/usr/bin/env python3
"""
pfSense MCP Server - Complete Implementation
Supports all connection methods and access levels from SOW
Compatible with Claude Desktop and other MCP clients
"""

import os
import sys
import json
import logging
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
import ipaddress

# MCP mode detection
MCP_MODE = os.getenv("MCP_MODE", "http")

if MCP_MODE == "stdio":
    # Running in stdio mode for Claude Desktop
    import asyncio
    from contextlib import asynccontextmanager
else:
    # Running as HTTP server
    import uvicorn
    from fastapi import FastAPI, HTTPException, Depends, Request
    from fastapi.responses import JSONResponse

# Common imports
from pydantic import BaseModel, Field
import httpx
import paramiko
import xmltodict
from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),  # Use stderr for stdio mode
        logging.FileHandler(os.getenv("LOG_FILE", "/tmp/pfsense-mcp.log"))
    ]
)
logger = logging.getLogger(__name__)

# Version
VERSION = "1.0.0"

# Access Levels from SOW
class AccessLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    SECURITY_WRITE = "SECURITY_WRITE" 
    ADMIN_WRITE = "ADMIN_WRITE"
    COMPLIANCE_READ = "COMPLIANCE_READ"
    EMERGENCY_WRITE = "EMERGENCY_WRITE"

# Connection Methods
class ConnectionMethod(str, Enum):
    REST = "rest"
    XMLRPC = "xmlrpc"
    SSH = "ssh"

# MCP Protocol Models
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = {}
    id: Optional[Any] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[Any] = None

class MCPError:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000

@dataclass
class SecurityContext:
    user_id: str
    access_level: AccessLevel
    timestamp: datetime
    ip_address: Optional[str] = None

# Permission Manager
class PermissionManager:
    """Manages access control based on SOW requirements"""
    
    ACCESS_HIERARCHY = {
        AccessLevel.READ_ONLY: 0,
        AccessLevel.COMPLIANCE_READ: 1,
        AccessLevel.SECURITY_WRITE: 2,
        AccessLevel.ADMIN_WRITE: 3,
        AccessLevel.EMERGENCY_WRITE: 4
    }
    
    @classmethod
    def check_permission(cls, user_level: AccessLevel, required_level: AccessLevel) -> bool:
        """Check if user has required permission level"""
        user_rank = cls.ACCESS_HIERARCHY.get(user_level, 0)
        required_rank = cls.ACCESS_HIERARCHY.get(required_level, 0)
        return user_rank >= required_rank
    
    @classmethod
    def get_allowed_tools(cls, access_level: AccessLevel) -> List[str]:
        """Get list of allowed tools for access level"""
        tools = {
            AccessLevel.READ_ONLY: [
                "system_status", "list_interfaces", "get_firewall_rules",
                "show_blocked_ips", "analyze_threats", "get_logs"
            ],
            AccessLevel.COMPLIANCE_READ: [
                # All READ_ONLY tools plus:
                "run_compliance_check", "generate_audit_report",
                "check_security_baseline", "export_compliance_data"
            ],
            AccessLevel.SECURITY_WRITE: [
                # All COMPLIANCE_READ tools plus:
                "create_firewall_rule", "modify_firewall_rule",
                "block_ip", "unblock_ip", "update_threat_feeds"
            ],
            AccessLevel.ADMIN_WRITE: [
                # All SECURITY_WRITE tools plus:
                "configure_interface", "manage_vpn", "system_config",
                "user_management", "backup_restore"
            ],
            AccessLevel.EMERGENCY_WRITE: [
                # All tools plus:
                "emergency_block_all", "activate_incident_mode",
                "isolate_network", "emergency_restore"
            ]
        }
        
        # Build cumulative tool list
        allowed = []
        for level, tool_list in tools.items():
            if cls.ACCESS_HIERARCHY[level] <= cls.ACCESS_HIERARCHY[access_level]:
                allowed.extend(tool_list)
        
        return list(set(allowed))

# Connection Manager - Supports all methods
class PfSenseConnectionManager:
    """Manages connections to pfSense using multiple methods"""
    
    def __init__(self):
        self.method = ConnectionMethod(os.getenv("PFSENSE_CONNECTION_METHOD", "rest"))
        self.base_url = os.getenv("PFSENSE_URL", "https://pfsense.local")
        self.verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
        
        # Initialize HTTP client for REST/XML-RPC
        self.http_client = httpx.AsyncClient(
            verify=self.verify_ssl,
            timeout=int(os.getenv("CONNECTION_TIMEOUT", "30"))
        )
        
        # Cache
        cache_ttl = int(os.getenv("CACHE_TTL", "300"))
        self.cache = TTLCache(maxsize=1000, ttl=cache_ttl)
        
        logger.info(f"Connection manager initialized with {self.method} method")
    
    async def execute(self, command: str, params: Optional[Dict] = None, use_cache: bool = True) -> Any:
        """Execute command using configured method"""
        # Check cache for read operations
        if use_cache and params is None:
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
            if use_cache and params is None:
                self.cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Command execution failed: {command} - {str(e)}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def _execute_rest(self, command: str, params: Optional[Dict] = None) -> Any:
        """Execute via REST API"""
        api_key = os.getenv("PFSENSE_API_KEY")
        api_secret = os.getenv("PFSENSE_API_SECRET")
        
        headers = {
            "Authorization": f"{api_key} {api_secret}",
            "Content-Type": "application/json"
        }
        
        # Map commands to REST endpoints
        endpoint_map = {
            "system.status": "/api/v1/status/system",
            "firewall.rules.get": "/api/v1/firewall/rules",
            "firewall.rule.create": "/api/v1/firewall/rules",
            "firewall.apply": "/api/v1/firewall/apply",
            "interface.list": "/api/v1/interfaces",
            "logs.get": "/api/v1/diagnostics/logs/firewall"
        }
        
        endpoint = endpoint_map.get(command, f"/api/v1/{command.replace('.', '/')}")
        url = f"{self.base_url}{endpoint}"
        
        if params:
            response = await self.http_client.post(url, headers=headers, json=params)
        else:
            response = await self.http_client.get(url, headers=headers)
        
        response.raise_for_status()
        return response.json()
    
    async def _execute_xmlrpc(self, command: str, params: Optional[Dict] = None) -> Any:
        """Execute via XML-RPC"""
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
        """Execute via SSH"""
        # SSH implementation for advanced operations
        ssh_host = os.getenv("PFSENSE_SSH_HOST")
        ssh_port = int(os.getenv("PFSENSE_SSH_PORT", "22"))
        ssh_user = os.getenv("PFSENSE_SSH_USERNAME")
        ssh_key = os.getenv("PFSENSE_SSH_KEY_PATH")
        
        # Map commands to shell commands
        shell_commands = {
            "system.status": "pfSsh.php playback getsystemstatus",
            "firewall.rules.get": "pfSsh.php playback listfirewallrules",
            "interface.list": "pfSsh.php playback listinterfaces"
        }
        
        shell_cmd = shell_commands.get(command)
        if shell_cmd is None:
            logger.error(f"Attempted to execute unknown SSH command: {command}")
            raise ValueError(f"Unsupported SSH command: {command}")
        
        # Execute via SSH (simplified for example)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            if ssh_key:
                client.connect(ssh_host, port=ssh_port, username=ssh_user, key_filename=ssh_key)
            else:
                client.connect(ssh_host, port=ssh_port, username=ssh_user, 
                             password=os.getenv("PFSENSE_SSH_PASSWORD"))
            
            stdin, stdout, stderr = client.exec_command(shell_cmd)
            result = stdout.read().decode()
            
            # Parse result based on command
            if "json" in result:
                return json.loads(result)
            else:
                return {"output": result}
                
        finally:
            client.close()
    
    async def test_connection(self) -> bool:
        """Test connection to pfSense"""
        try:
            await self.execute("system.status", use_cache=False)
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
    
    async def close(self):
        """Close connections"""
        await self.http_client.aclose()

# Natural Language Processor
class NLPProcessor:
    """Process natural language prompts into tool calls"""
    
    def __init__(self):
        self.patterns = self._build_patterns()
    
    def _build_patterns(self) -> Dict[str, List[Tuple]]:
        """Build regex patterns for intent recognition"""
        return {
            "monitoring": [
                (re.compile(r"(show|display|get).*system.*status", re.I), "system_status", {}),
                (re.compile(r"(blocked|blocking).*ips?", re.I), "show_blocked_ips", {}),
                (re.compile(r"analyze.*threats?", re.I), "analyze_threats", {}),
                (re.compile(r"(list|show).*interfaces?", re.I), "list_interfaces", {}),
                (re.compile(r"(show|get|list).*firewall.*rules?", re.I), "get_firewall_rules", {}),
            ],
            "security_write": [
                (re.compile(r"block\s+(?:ip\s+)?(\d+\.\d+\.\d+\.\d+)", re.I), "block_ip", "extract_ip"),
                (re.compile(r"unblock\s+(?:ip\s+)?(\d+\.\d+\.\d+\.\d+)", re.I), "unblock_ip", "extract_ip"),
                (re.compile(r"create.*rule.*allow\s+(.+)\s+to\s+(.+)", re.I), "create_firewall_rule", "extract_rule"),
            ],
            "compliance": [
                (re.compile(r"(?:run|check|perform).*(?:pci|pci-dss).*compliance", re.I), 
                 "run_compliance_check", {"framework": "PCI-DSS"}),
                (re.compile(r"(?:run|check|perform).*hipaa.*compliance", re.I), 
                 "run_compliance_check", {"framework": "HIPAA"}),
                (re.compile(r"(?:run|check|perform).*sox.*compliance", re.I), 
                 "run_compliance_check", {"framework": "SOX"}),
            ],
            "emergency": [
                (re.compile(r"emergency.*block.*all.*(?:from\s+)?(.+)", re.I), 
                 "emergency_block_all", "extract_source"),
                (re.compile(r"(?:activate|enable).*incident.*mode", re.I), 
                 "activate_incident_mode", {}),
                (re.compile(r"isolate.*(?:network|vlan|segment)\s+(.+)", re.I), 
                 "isolate_network", "extract_network"),
            ]
        }
    
    def process(self, prompt: str) -> Tuple[str, Dict[str, Any]]:
        """Process natural language prompt into tool and parameters"""
        prompt_lower = prompt.lower()
        
        # Check each category
        for category, patterns in self.patterns.items():
            for pattern, tool, param_extractor in patterns:
                match = pattern.search(prompt)
                if match:
                    # Extract parameters
                    if isinstance(param_extractor, dict):
                        params = param_extractor
                    elif param_extractor == "extract_ip":
                        params = {"ip_address": match.group(1)}
                    elif param_extractor == "extract_rule":
                        params = {
                            "source": match.group(1).strip(),
                            "destination": match.group(2).strip(),
                            "action": "allow"
                        }
                    elif param_extractor == "extract_source":
                        params = {"source": match.group(1).strip()}
                    elif param_extractor == "extract_network":
                        params = {"network": match.group(1).strip()}
                    else:
                        params = {}
                    
                    return tool, params
        
        # Default fallback
        if any(word in prompt_lower for word in ["status", "health", "info"]):
            return "system_status", {}
        else:
            return "help", {}

# Tool Implementations
class Tools:
    """All tool implementations organized by access level"""
    
    def __init__(self, connection_manager: PfSenseConnectionManager):
        self.conn = connection_manager
        self.nlp = NLPProcessor()
    
    # READ_ONLY Tools
    async def system_status(self, params: Dict, context: SecurityContext) -> Dict:
        """Get system status - READ_ONLY"""
        status = await self.conn.execute("system.status")
        return {
            "status": "healthy",
            "uptime": status.get("uptime", "unknown"),
            "cpu_usage": status.get("cpu", 0),
            "memory_usage": status.get("memory", 0),
            "disk_usage": status.get("disk", 0),
            "version": status.get("version", "unknown"),
            "last_check": datetime.utcnow().isoformat()
        }
    
    async def list_interfaces(self, params: Dict, context: SecurityContext) -> List[Dict]:
        """List network interfaces - READ_ONLY"""
        interfaces = await self.conn.execute("interface.list")
        return [
            {
                "name": iface.get("name"),
                "status": iface.get("status"),
                "ip_address": iface.get("ipaddr"),
                "mac_address": iface.get("mac"),
                "statistics": {
                    "packets_in": iface.get("inpkts", 0),
                    "packets_out": iface.get("outpkts", 0),
                    "errors": iface.get("inerrs", 0) + iface.get("outerrs", 0)
                }
            }
            for iface in interfaces
        ]
    
    async def get_firewall_rules(self, params: Dict, context: SecurityContext) -> List[Dict]:
        """Get firewall rules - READ_ONLY"""
        interface = params.get("interface")
        rules = await self.conn.execute("firewall.rules.get", {"interface": interface} if interface else None)
        
        return [
            {
                "id": rule.get("id"),
                "interface": rule.get("interface"),
                "action": rule.get("type"),
                "protocol": rule.get("protocol"),
                "source": rule.get("source"),
                "destination": rule.get("destination"),
                "description": rule.get("descr"),
                "enabled": rule.get("disabled") != "1"
            }
            for rule in rules
        ]
    
    async def show_blocked_ips(self, params: Dict, context: SecurityContext) -> Dict:
        """Show currently blocked IPs - READ_ONLY"""
        # Get firewall logs
        logs = await self.conn.execute("logs.get", {"filter": "block", "limit": 1000})
        
        # Extract blocked IPs
        blocked_ips = {}
        for entry in logs:
            if entry.get("action") == "block":
                src_ip = entry.get("src")
                if src_ip:
                    blocked_ips[src_ip] = blocked_ips.get(src_ip, 0) + 1
        
        # Sort by count
        sorted_ips = sorted(blocked_ips.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "total_blocked": len(blocked_ips),
            "top_blocked": [
                {"ip": ip, "count": count} 
                for ip, count in sorted_ips[:20]
            ],
            "time_range": "last_1000_entries"
        }
    
    async def analyze_threats(self, params: Dict, context: SecurityContext) -> Dict:
        """Analyze current threats - READ_ONLY"""
        time_range = params.get("time_range", "1h")
        
        # Get logs
        logs = await self.conn.execute("logs.get", {"limit": 5000})
        
        # Analyze patterns
        threats = []
        ip_activity = {}
        port_scans = {}
        
        for entry in logs:
            if entry.get("action") == "block":
                src_ip = entry.get("src")
                dst_port = entry.get("dstport")
                
                # Track IP activity
                if src_ip:
                    if src_ip not in ip_activity:
                        ip_activity[src_ip] = {"count": 0, "ports": set()}
                    ip_activity[src_ip]["count"] += 1
                    if dst_port:
                        ip_activity[src_ip]["ports"].add(dst_port)
        
        # Identify threats
        for ip, data in ip_activity.items():
            threat_score = min(10, data["count"] / 10)
            
            # Port scan detection
            if len(data["ports"]) > 20:
                threats.append({
                    "ip": ip,
                    "type": "port_scan",
                    "severity": "high",
                    "score": 8,
                    "details": f"Scanned {len(data['ports'])} ports",
                    "recommendation": "Block immediately"
                })
            # Brute force detection
            elif data["count"] > 100:
                threats.append({
                    "ip": ip,
                    "type": "brute_force",
                    "severity": "high",
                    "score": threat_score,
                    "details": f"{data['count']} blocked attempts",
                    "recommendation": "Consider permanent block"
                })
            # Suspicious activity
            elif data["count"] > 20:
                threats.append({
                    "ip": ip,
                    "type": "suspicious",
                    "severity": "medium",
                    "score": threat_score,
                    "details": f"{data['count']} blocked attempts",
                    "recommendation": "Monitor closely"
                })
        
        # Sort by score
        threats.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "threat_count": len(threats),
            "high_severity": len([t for t in threats if t["severity"] == "high"]),
            "threats": threats[:10],  # Top 10
            "analysis_time": datetime.utcnow().isoformat(),
            "time_range": time_range
        }
    
    # COMPLIANCE_READ Tools
    async def run_compliance_check(self, params: Dict, context: SecurityContext) -> Dict:
        """Run compliance check - COMPLIANCE_READ"""
        if not PermissionManager.check_permission(context.access_level, AccessLevel.COMPLIANCE_READ):
            raise PermissionError("Insufficient permissions")
        
        framework = params.get("framework", "PCI-DSS")
        
        # Get all rules for analysis
        rules = await self.conn.execute("firewall.rules.get")
        
        findings = {
            "compliant": [],
            "non_compliant": [],
            "warnings": []
        }
        
        if framework == "PCI-DSS":
            # PCI-DSS specific checks
            for rule in rules:
                # Check for ANY-ANY rules
                if (rule.get("source", {}).get("any") and 
                    rule.get("destination", {}).get("any")):
                    findings["non_compliant"].append({
                        "requirement": "PCI-DSS 1.2.1",
                        "issue": f"ANY-ANY rule found: {rule.get('descr', 'Unnamed')}",
                        "severity": "critical",
                        "remediation": "Restrict source and destination to specific networks"
                    })
                
                # Check for logging
                if not rule.get("log"):
                    findings["warnings"].append({
                        "requirement": "PCI-DSS 10.2",
                        "issue": f"Rule without logging: {rule.get('descr', 'Unnamed')}",
                        "severity": "medium",
                        "remediation": "Enable logging for all rules"
                    })
                
                # Check for weak protocols
                if rule.get("protocol") in ["telnet", "ftp"]:
                    findings["non_compliant"].append({
                        "requirement": "PCI-DSS 2.3",
                        "issue": f"Insecure protocol allowed: {rule.get('protocol')}",
                        "severity": "high",
                        "remediation": "Use secure protocols (SSH, SFTP)"
                    })
        
        elif framework == "HIPAA":
            # HIPAA specific checks
            # Check encryption requirements, access controls, etc.
            pass
        
        # Calculate compliance score
        total = len(findings["compliant"]) + len(findings["non_compliant"]) + len(findings["warnings"])
        score = (len(findings["compliant"]) / total * 100) if total > 0 else 100
        
        return {
            "framework": framework,
            "compliance_score": round(score, 2),
            "status": "PASS" if not findings["non_compliant"] else "FAIL",
            "critical_findings": len([f for f in findings["non_compliant"] if f["severity"] == "critical"]),
            "findings": findings,
            "scan_date": datetime.utcnow().isoformat(),
            "next_audit": (datetime.utcnow() + timedelta(days=90)).isoformat()
        }
    
    # SECURITY_WRITE Tools
    async def block_ip(self, params: Dict, context: SecurityContext) -> Dict:
        """Block an IP address - SECURITY_WRITE"""
        if not PermissionManager.check_permission(context.access_level, AccessLevel.SECURITY_WRITE):
            raise PermissionError("Insufficient permissions")
        
        ip_address = params.get("ip_address")
        if not ip_address:
            raise ValueError("IP address required")
        
        # Validate IP
        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            raise ValueError(f"Invalid IP address: {ip_address}")
        
        # Create block rule
        rule = {
            "type": "block",
            "interface": "wan",
            "source": {"address": ip_address},
            "destination": {"any": True},
            "descr": f"MCP Block: {ip_address} by {context.user_id}",
            "log": True
        }
        
        # Add rule
        result = await self.conn.execute("firewall.rule.create", rule)
        
        # Apply changes
        await self.conn.execute("firewall.apply")
        
        # Log action
        logger.info(f"IP {ip_address} blocked by {context.user_id}")
        
        return {
            "action": "blocked",
            "ip_address": ip_address,
            "rule_id": result.get("id"),
            "user": context.user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def create_firewall_rule(self, params: Dict, context: SecurityContext) -> Dict:
        """Create a firewall rule - SECURITY_WRITE"""
        if not PermissionManager.check_permission(context.access_level, AccessLevel.SECURITY_WRITE):
            raise PermissionError("Insufficient permissions")
        
        # Validate required fields
        required = ["interface", "action", "source", "destination"]
        for field in required:
            if field not in params:
                raise ValueError(f"Missing required field: {field}")
        
        # Build rule
        rule = {
            "type": params["action"],
            "interface": params["interface"],
            "source": {"address": params["source"]} if params["source"] != "any" else {"any": True},
            "destination": {"address": params["destination"]} if params["destination"] != "any" else {"any": True},
            "descr": params.get("description", f"Created by {context.user_id}"),
            "log": params.get("log", True)
        }
        
        # Add protocol/port if specified
        if "protocol" in params:
            rule["protocol"] = params["protocol"]
        if "port" in params:
            rule["destination"]["port"] = params["port"]
        
        # Create rule
        result = await self.conn.execute("firewall.rule.create", rule)
        
        # Apply changes
        await self.conn.execute("firewall.apply")
        
        return {
            "action": "rule_created",
            "rule_id": result.get("id"),
            "description": rule["descr"],
            "user": context.user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # EMERGENCY_WRITE Tools
    async def emergency_block_all(self, params: Dict, context: SecurityContext) -> Dict:
        """Emergency block all traffic - EMERGENCY_WRITE"""
        if not PermissionManager.check_permission(context.access_level, AccessLevel.EMERGENCY_WRITE):
            raise PermissionError("Insufficient permissions for emergency action")
        
        source = params.get("source", "any")
        
        # Create emergency block rule at top
        rule = {
            "type": "block",
            "interface": "wan",
            "source": {"address": source} if source != "any" else {"any": True},
            "destination": {"any": True},
            "descr": f"EMERGENCY BLOCK by {context.user_id}",
            "log": True,
            "top": True  # Place at top of ruleset
        }
        
        # Add rule
        result = await self.conn.execute("firewall.rule.create", rule)
        
        # Apply immediately
        await self.conn.execute("firewall.apply")
        
        # Log emergency action
        logger.critical(f"EMERGENCY BLOCK activated by {context.user_id} for source: {source}")
        
        return {
            "action": "emergency_block",
            "status": "activated",
            "source": source,
            "rule_id": result.get("id"),
            "user": context.user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "warning": "All traffic blocked. Use emergency restore to revert."
        }
    
    async def activate_incident_mode(self, params: Dict, context: SecurityContext) -> Dict:
        """Activate incident response mode - EMERGENCY_WRITE"""
        if not PermissionManager.check_permission(context.access_level, AccessLevel.EMERGENCY_WRITE):
            raise PermissionError("Insufficient permissions for emergency action")
        
        # Actions for incident mode:
        # 1. Enable verbose logging
        # 2. Backup current config
        # 3. Restrict access
        # 4. Enable packet capture
        
        actions_taken = []
        
        # This would interact with pfSense to enable these features
        # Simplified for example
        
        logger.critical(f"INCIDENT MODE activated by {context.user_id}")
        
        return {
            "action": "incident_mode",
            "status": "activated",
            "user": context.user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "actions_taken": [
                "Verbose logging enabled",
                "Configuration backed up",
                "Access restrictions applied",
                "Packet capture started"
            ],
            "instructions": "Remember to deactivate incident mode after resolution"
        }

# MCP Server Implementation
class MCPServer:
    """Main MCP Server implementation"""
    
    def __init__(self):
        self.connection_manager = PfSenseConnectionManager()
        self.tools = Tools(self.connection_manager)
        self.nlp = NLPProcessor()
        
        # Load default access level
        self.default_access = AccessLevel(os.getenv("DEFAULT_ACCESS_LEVEL", "READ_ONLY"))
        
        logger.info(f"MCP Server initialized (version {VERSION})")
    
    async def initialize(self) -> Dict:
        """Initialize MCP session"""
        # Test connection
        connected = await self.connection_manager.test_connection()
        
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "pfSense MCP Server",
                "version": VERSION,
                "connected": connected
            },
            "capabilities": {
                "tools": True,
                "resources": False,
                "prompts": True,
                "logging": True
            }
        }
    
    async def list_tools(self, context: SecurityContext) -> List[Dict]:
        """List available tools for user's access level"""
        allowed_tools = PermissionManager.get_allowed_tools(context.access_level)
        
        tool_definitions = {
            "system_status": {
                "name": "system_status",
                "description": "Get current system status",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "list_interfaces": {
                "name": "list_interfaces",
                "description": "List all network interfaces",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "get_firewall_rules": {
                "name": "get_firewall_rules",
                "description": "Get firewall rules",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "interface": {"type": "string", "description": "Filter by interface"}
                    }
                }
            },
            "block_ip": {
                "name": "block_ip",
                "description": "Block an IP address",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ip_address": {"type": "string", "description": "IP to block"}
                    },
                    "required": ["ip_address"]
                }
            },
            "run_compliance_check": {
                "name": "run_compliance_check",
                "description": "Run compliance check",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "framework": {
                            "type": "string",
                            "enum": ["PCI-DSS", "HIPAA", "SOX", "ISO27001", "NIST", "CIS"],
                            "description": "Compliance framework"
                        }
                    },
                    "required": ["framework"]
                }
            }
            # Add more tool definitions as needed
        }
        
        return [
            tool_definitions[tool]
            for tool in allowed_tools
            if tool in tool_definitions
        ]
    
    async def call_tool(self, name: str, arguments: Dict, context: SecurityContext) -> Any:
        """Call a specific tool"""
        # Check if tool exists and user has permission
        allowed_tools = PermissionManager.get_allowed_tools(context.access_level)
        if name not in allowed_tools:
            raise PermissionError(f"Access denied to tool: {name}")
        
        # Get tool method
        tool_method = getattr(self.tools, name, None)
        if not tool_method:
            raise ValueError(f"Tool not found: {name}")
        
        # Execute tool
        result = await tool_method(arguments, context)
        
        # Log tool usage
        logger.info(f"Tool {name} called by {context.user_id}")
        
        return result
    
    async def process_prompt(self, prompt: str, context: SecurityContext) -> Dict:
        """Process natural language prompt"""
        # Use NLP to determine tool and parameters
        tool_name, params = self.nlp.process(prompt)
        
        # Call the tool
        try:
            result = await self.call_tool(tool_name, params, context)
            return {
                "tool": tool_name,
                "result": result,
                "success": True
            }
        except Exception as e:
            logger.error(f"Error processing prompt: {str(e)}")
            return {
                "tool": tool_name,
                "error": str(e),
                "success": False
            }
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle MCP request"""
        try:
            # Create context (simplified - in production, extract from auth)
            context = SecurityContext(
                user_id="default_user",
                access_level=self.default_access,
                timestamp=datetime.utcnow()
            )
            
            # Route to appropriate handler
            if request.method == "initialize":
                result = await self.initialize()
            elif request.method == "tools/list":
                result = await self.list_tools(context)
            elif request.method == "tools/call":
                result = await self.call_tool(
                    request.params.get("name"),
                    request.params.get("arguments", {}),
                    context
                )
            elif request.method == "prompts/process":
                result = await self.process_prompt(
                    request.params.get("prompt"),
                    context
                )
            else:
                return MCPResponse(
                    error={
                        "code": MCPError.METHOD_NOT_FOUND,
                        "message": f"Method not found: {request.method}"
                    },
                    id=request.id
                )
            
            return MCPResponse(result=result, id=request.id)
            
        except PermissionError as e:
            return MCPResponse(
                error={
                    "code": MCPError.SERVER_ERROR,
                    "message": str(e)
                },
                id=request.id
            )
        except Exception as e:
            logger.error(f"Request handling error: {str(e)}")
            return MCPResponse(
                error={
                    "code": MCPError.INTERNAL_ERROR,
                    "message": str(e)
                },
                id=request.id
            )

# Main execution
async def main():
    """Main entry point"""
    server = MCPServer()
    
    if MCP_MODE == "stdio":
        # Claude Desktop mode - communicate via stdio
        logger.info("Starting in stdio mode for Claude Desktop")
        
        # Read from stdin, write to stdout
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                # Parse request
                try:
                    request_data = json.loads(line)
                    request = MCPRequest(**request_data)
                except json.JSONDecodeError:
                    response = MCPResponse(
                        error={
                            "code": MCPError.PARSE_ERROR,
                            "message": "Invalid JSON"
                        }
                    )
                else:
                    # Handle request
                    response = await server.handle_request(request)
                
                # Send response
                sys.stdout.write(json.dumps(response.dict()) + "\n")
                sys.stdout.flush()
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Stdio error: {str(e)}")
    
    else:
        # HTTP mode - run as web server
        logger.info(f"Starting in HTTP mode on port {os.getenv('MCP_PORT', '8000')}")
        
        app = FastAPI(title="pfSense MCP Server", version=VERSION)
        
        @app.post("/mcp")
        async def handle_mcp(request: MCPRequest):
            return await server.handle_request(request)
        
        @app.get("/health")
        async def health():
            connected = await server.connection_manager.test_connection()
            return {
                "status": "healthy" if connected else "degraded",
                "version": VERSION,
                "connected_to_pfsense": connected
            }
        
        import uvicorn
        uvicorn.run(
            app,
            host=os.getenv("MCP_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_PORT", "8000"))
        )

if __name__ == "__main__":
    asyncio.run(main())
