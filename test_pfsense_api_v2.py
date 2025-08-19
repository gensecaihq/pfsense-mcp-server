#!/usr/bin/env python3
"""
Test script for pfSense API v2 integration
Validates connection and basic functionality
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Dict, Any

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pfsense_api_integration import (
    PfSenseAPIv2Client,
    AuthMethod,
    PfSenseVersion
)

class TestResults:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
    
    def add_test(self, name: str, success: bool, message: str, data: Any = None):
        self.tests.append({
            "name": name,
            "success": success,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })
        if success:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_results(self):
        print(f"\n{'='*60}")
        print(f"TEST RESULTS: {self.passed} passed, {self.failed} failed")
        print(f"{'='*60}")
        
        for test in self.tests:
            status = "✅ PASS" if test["success"] else "❌ FAIL"
            print(f"{status} {test['name']}")
            print(f"    {test['message']}")
            if not test["success"] and test["data"]:
                print(f"    Error: {test['data']}")
            print()

async def test_pfsense_api():
    """Test pfSense API v2 integration"""
    results = TestResults()
    
    # Load configuration from environment or defaults
    host = os.getenv("PFSENSE_URL", "https://pfsense.local")
    api_key = os.getenv("PFSENSE_API_KEY")
    username = os.getenv("PFSENSE_USERNAME")
    password = os.getenv("PFSENSE_PASSWORD")
    verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
    
    # Determine version
    version_str = os.getenv("PFSENSE_VERSION", "CE_2_8_0")
    if version_str == "PLUS_24_11":
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
    
    print(f"Testing pfSense API v2 Integration")
    print(f"Host: {host}")
    print(f"Version: {version.value}")
    print(f"Auth Method: {auth_method.value}")
    print(f"SSL Verification: {verify_ssl}")
    print(f"{'='*60}")
    
    # Initialize client
    try:
        client = PfSenseAPIv2Client(
            host=host,
            auth_method=auth_method,
            username=username,
            password=password,
            api_key=api_key,
            verify_ssl=verify_ssl,
            version=version,
            timeout=30
        )
        results.add_test(
            "Client Initialization",
            True,
            "API client created successfully"
        )
    except Exception as e:
        results.add_test(
            "Client Initialization",
            False,
            "Failed to create API client",
            str(e)
        )
        results.print_results()
        return False
    
    # Test connection
    try:
        connected = await client.test_connection()
        if connected:
            results.add_test(
                "Connection Test",
                True,
                "Successfully connected to pfSense API"
            )
        else:
            results.add_test(
                "Connection Test",
                False,
                "Failed to connect to pfSense API"
            )
            results.print_results()
            return False
    except Exception as e:
        results.add_test(
            "Connection Test",
            False,
            "Connection test threw exception",
            str(e)
        )
        results.print_results()
        return False
    
    # Test system status
    try:
        status = await client.get_system_status()
        if status and "data" in status:
            results.add_test(
                "System Status",
                True,
                f"Retrieved system status successfully"
            )
        else:
            results.add_test(
                "System Status",
                False,
                "System status returned empty or invalid data",
                status
            )
    except Exception as e:
        results.add_test(
            "System Status",
            False,
            "Failed to get system status",
            str(e)
        )
    
    # Test interfaces
    try:
        interfaces = await client.get_interfaces()
        if isinstance(interfaces, list):
            results.add_test(
                "Interface List",
                True,
                f"Retrieved {len(interfaces)} interfaces"
            )
        else:
            results.add_test(
                "Interface List",
                False,
                "Interface list returned invalid data",
                interfaces
            )
    except Exception as e:
        results.add_test(
            "Interface List",
            False,
            "Failed to get interface list",
            str(e)
        )
    
    # Test firewall rules
    try:
        rules = await client.get_firewall_rules()
        if isinstance(rules, list):
            results.add_test(
                "Firewall Rules",
                True,
                f"Retrieved {len(rules)} firewall rules"
            )
        else:
            results.add_test(
                "Firewall Rules",
                False,
                "Firewall rules returned invalid data",
                rules
            )
    except Exception as e:
        results.add_test(
            "Firewall Rules",
            False,
            "Failed to get firewall rules",
            str(e)
        )
    
    # Test aliases
    try:
        aliases = await client.get_aliases()
        if isinstance(aliases, list):
            results.add_test(
                "Aliases",
                True,
                f"Retrieved {len(aliases)} aliases"
            )
        else:
            results.add_test(
                "Aliases",
                False,
                "Aliases returned invalid data",
                aliases
            )
    except Exception as e:
        results.add_test(
            "Aliases",
            False,
            "Failed to get aliases",
            str(e)
        )
    
    # Test services
    try:
        services = await client.get_services_status()
        if isinstance(services, list):
            results.add_test(
                "Services Status",
                True,
                f"Retrieved {len(services)} services"
            )
        else:
            results.add_test(
                "Services Status",
                False,
                "Services returned invalid data",
                services
            )
    except Exception as e:
        results.add_test(
            "Services Status",
            False,
            "Failed to get services status",
            str(e)
        )
    
    # Test DHCP leases
    try:
        leases = await client.get_dhcp_leases()
        if isinstance(leases, list):
            results.add_test(
                "DHCP Leases",
                True,
                f"Retrieved {len(leases)} DHCP leases"
            )
        else:
            results.add_test(
                "DHCP Leases",
                False,
                "DHCP leases returned invalid data",
                leases
            )
    except Exception as e:
        results.add_test(
            "DHCP Leases",
            False,
            "Failed to get DHCP leases",
            str(e)
        )
    
    # Test VPN status
    try:
        ipsec = await client.get_ipsec_status()
        results.add_test(
            "IPsec Status",
            True,
            "Retrieved IPsec status"
        )
    except Exception as e:
        results.add_test(
            "IPsec Status",
            False,
            "Failed to get IPsec status",
            str(e)
        )
    
    try:
        openvpn = await client.get_openvpn_status()
        if isinstance(openvpn, list):
            results.add_test(
                "OpenVPN Status",
                True,
                f"Retrieved OpenVPN status for {len(openvpn)} servers"
            )
        else:
            results.add_test(
                "OpenVPN Status",
                False,
                "OpenVPN status returned invalid data",
                openvpn
            )
    except Exception as e:
        results.add_test(
            "OpenVPN Status",
            False,
            "Failed to get OpenVPN status",
            str(e)
        )
    
    # Test diagnostics
    try:
        arp = await client.get_arp_table()
        if isinstance(arp, list):
            results.add_test(
                "ARP Table",
                True,
                f"Retrieved {len(arp)} ARP entries"
            )
        else:
            results.add_test(
                "ARP Table",
                False,
                "ARP table returned invalid data",
                arp
            )
    except Exception as e:
        results.add_test(
            "ARP Table",
            False,
            "Failed to get ARP table",
            str(e)
        )
    
    # Test API settings
    try:
        settings = await client.get_api_settings()
        results.add_test(
            "API Settings",
            True,
            "Retrieved API settings"
        )
    except Exception as e:
        results.add_test(
            "API Settings",
            False,
            "Failed to get API settings",
            str(e)
        )
    
    # Test OpenAPI schema
    try:
        schema = await client.get_openapi_schema()
        if schema and "openapi" in schema:
            results.add_test(
                "OpenAPI Schema",
                True,
                f"Retrieved OpenAPI schema (version {schema.get('openapi', 'unknown')})"
            )
        else:
            results.add_test(
                "OpenAPI Schema",
                False,
                "OpenAPI schema returned invalid data",
                schema
            )
    except Exception as e:
        results.add_test(
            "OpenAPI Schema",
            False,
            "Failed to get OpenAPI schema",
            str(e)
        )
    
    # Close client
    await client.close()
    results.add_test(
        "Client Cleanup",
        True,
        "Client closed successfully"
    )
    
    # Print results
    results.print_results()
    
    # Return overall success
    return results.failed == 0

async def test_mcp_tools():
    """Test MCP tools functionality"""
    print(f"\nTesting MCP Tools")
    print(f"{'='*60}")
    
    # Import MCP tools
    try:
        from main_pfsense_api_v2 import (
            system_status,
            list_interfaces,
            list_firewall_rules,
            test_connection,
            get_api_info
        )
        print("✅ MCP tools imported successfully")
    except Exception as e:
        print(f"❌ Failed to import MCP tools: {e}")
        return False
    
    # Test basic tools
    tools_to_test = [
        ("test_connection", test_connection),
        ("system_status", system_status),
        ("list_interfaces", list_interfaces),
        ("list_firewall_rules", list_firewall_rules),
        ("get_api_info", get_api_info)
    ]
    
    for tool_name, tool_func in tools_to_test:
        try:
            result = await tool_func()
            if result.get("success"):
                print(f"✅ {tool_name}: {result.get('message', 'Success')}")
            else:
                print(f"❌ {tool_name}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ {tool_name}: Exception - {e}")
    
    return True

def print_config_help():
    """Print configuration help"""
    print(f"\n{'='*60}")
    print("CONFIGURATION HELP")
    print(f"{'='*60}")
    print("Set these environment variables:")
    print()
    print("Required:")
    print("  PFSENSE_URL=https://your-pfsense.local")
    print("  PFSENSE_API_KEY=your-api-key-here")
    print()
    print("Optional:")
    print("  PFSENSE_VERSION=CE_2_8_0  # or PLUS_24_11")
    print("  AUTH_METHOD=api_key       # or basic, jwt")
    print("  VERIFY_SSL=true           # or false for testing")
    print()
    print("For basic auth:")
    print("  PFSENSE_USERNAME=admin")
    print("  PFSENSE_PASSWORD=your-password")
    print()
    print("Example:")
    print("  export PFSENSE_URL=https://192.168.1.1")
    print("  export PFSENSE_API_KEY=abc123...")
    print("  python test_pfsense_api_v2.py")

def main():
    """Main test function"""
    print("pfSense API v2 Integration Test")
    print(f"{'='*60}")
    
    # Check if we have basic configuration
    if not os.getenv("PFSENSE_URL"):
        print("❌ Missing PFSENSE_URL environment variable")
        print_config_help()
        return 1
    
    if not os.getenv("PFSENSE_API_KEY") and not (os.getenv("PFSENSE_USERNAME") and os.getenv("PFSENSE_PASSWORD")):
        print("❌ Missing authentication credentials")
        print("   Need either PFSENSE_API_KEY or PFSENSE_USERNAME+PFSENSE_PASSWORD")
        print_config_help()
        return 1
    
    # Run tests
    try:
        # Test API integration
        api_success = asyncio.run(test_pfsense_api())
        
        # Test MCP tools
        mcp_success = asyncio.run(test_mcp_tools())
        
        if api_success and mcp_success:
            print(f"\n🎉 ALL TESTS PASSED! Your pfSense API v2 integration is working.")
            return 0
        else:
            print(f"\n❌ Some tests failed. Check the output above for details.")
            return 1
            
    except KeyboardInterrupt:
        print(f"\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())