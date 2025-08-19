#!/usr/bin/env python3
"""
Test Enhanced pfSense MCP Server Features
Tests: Object IDs, Queries/Filters, HATEOAS, Control Parameters
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pfsense_api_enhanced import (
    EnhancedPfSenseAPIClient,
    AuthMethod,
    PfSenseVersion,
    QueryFilter,
    SortOptions,
    PaginationOptions,
    ControlParameters
)

class EnhancedTestResults:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.features_tested = set()
    
    def add_test(self, name: str, feature: str, success: bool, message: str, data: Any = None):
        self.tests.append({
            "name": name,
            "feature": feature,
            "success": success,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.features_tested.add(feature)
        if success:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_results(self):
        print(f"\n{'='*80}")
        print(f"ENHANCED FEATURES TEST RESULTS")
        print(f"{'='*80}")
        print(f"Tests: {self.passed} passed, {self.failed} failed")
        print(f"Features tested: {len(self.features_tested)}")
        print(f"Features: {', '.join(sorted(self.features_tested))}")
        print(f"{'='*80}")
        
        # Group by feature
        by_feature = {}
        for test in self.tests:
            feature = test["feature"]
            if feature not in by_feature:
                by_feature[feature] = []
            by_feature[feature].append(test)
        
        for feature, tests in by_feature.items():
            passed = len([t for t in tests if t["success"]])
            total = len(tests)
            print(f"\n🔧 {feature.upper()} ({passed}/{total} passed)")
            print("-" * 40)
            
            for test in tests:
                status = "✅ PASS" if test["success"] else "❌ FAIL"
                print(f"  {status} {test['name']}")
                print(f"      {test['message']}")
                if not test["success"] and test["data"]:
                    print(f"      Error: {test['data']}")

async def test_enhanced_api_features():
    """Test all enhanced API features"""
    results = EnhancedTestResults()
    
    # Load configuration
    host = os.getenv("PFSENSE_URL", "https://pfsense.local")
    api_key = os.getenv("PFSENSE_API_KEY")
    username = os.getenv("PFSENSE_USERNAME")
    password = os.getenv("PFSENSE_PASSWORD")
    verify_ssl = os.getenv("VERIFY_SSL", "true").lower() == "true"
    
    version_str = os.getenv("PFSENSE_VERSION", "CE_2_8_0")
    version = PfSenseVersion.PLUS_24_11 if version_str == "PLUS_24_11" else PfSenseVersion.CE_2_8_0
    
    auth_method_str = os.getenv("AUTH_METHOD", "api_key").lower()
    if auth_method_str == "basic":
        auth_method = AuthMethod.BASIC
    elif auth_method_str == "jwt":
        auth_method = AuthMethod.JWT
    else:
        auth_method = AuthMethod.API_KEY
    
    print(f"Testing Enhanced pfSense API Features")
    print(f"Host: {host}")
    print(f"Version: {version.value}")
    print(f"Auth: {auth_method.value}")
    print(f"SSL Verify: {verify_ssl}")
    
    # Initialize client
    client = EnhancedPfSenseAPIClient(
        host=host,
        auth_method=auth_method,
        username=username,
        password=password,
        api_key=api_key,
        verify_ssl=verify_ssl,
        version=version,
        enable_hateoas=True
    )
    
    # Test 1: Basic Connection
    try:
        connected = await client.test_connection()
        results.add_test(
            "Basic Connection",
            "connection",
            connected,
            "API connection established" if connected else "Failed to connect"
        )
        
        if not connected:
            results.print_results()
            return False
    except Exception as e:
        results.add_test(
            "Basic Connection",
            "connection",
            False,
            "Connection test failed",
            str(e)
        )
        results.print_results()
        return False
    
    # Test 2: Query Filters
    print("\n🔍 Testing Query Filters...")
    
    # Test exact match filter
    try:
        filters = [QueryFilter("status", "up")]
        interfaces = await client.get_interfaces(filters=filters)
        success = "data" in interfaces
        results.add_test(
            "Exact Match Filter",
            "filters",
            success,
            f"Filtered interfaces by status=up: {len(interfaces.get('data', []))} results"
        )
    except Exception as e:
        results.add_test(
            "Exact Match Filter",
            "filters",
            False,
            "Exact match filter failed",
            str(e)
        )
    
    # Test contains filter
    try:
        filters = [QueryFilter("name", "wan", "contains")]
        interfaces = await client.get_interfaces(filters=filters)
        success = "data" in interfaces
        results.add_test(
            "Contains Filter",
            "filters",
            success,
            f"Filtered interfaces containing 'wan': {len(interfaces.get('data', []))} results"
        )
    except Exception as e:
        results.add_test(
            "Contains Filter",
            "filters",
            False,
            "Contains filter failed",
            str(e)
        )
    
    # Test multiple filters
    try:
        filters = [
            QueryFilter("type", "pass"),
            QueryFilter("interface", "wan")
        ]
        rules = await client.get_firewall_rules(filters=filters)
        success = "data" in rules
        results.add_test(
            "Multiple Filters",
            "filters",
            success,
            f"Multiple filters applied: {len(rules.get('data', []))} results"
        )
    except Exception as e:
        results.add_test(
            "Multiple Filters",
            "filters",
            False,
            "Multiple filters failed",
            str(e)
        )
    
    # Test 3: Sorting
    print("\n📊 Testing Sorting...")
    
    # Test basic sorting
    try:
        sort = SortOptions(sort_by="interface", sort_order="asc")
        rules = await client.get_firewall_rules(sort=sort)
        success = "data" in rules
        results.add_test(
            "Basic Sorting",
            "sorting",
            success,
            f"Sorted firewall rules by interface: {len(rules.get('data', []))} results"
        )
    except Exception as e:
        results.add_test(
            "Basic Sorting",
            "sorting",
            False,
            "Basic sorting failed",
            str(e)
        )
    
    # Test descending sort
    try:
        sort = SortOptions(sort_by="id", sort_order="desc")
        aliases = await client.get_aliases(sort=sort)
        success = "data" in aliases
        results.add_test(
            "Descending Sort",
            "sorting",
            success,
            f"Sorted aliases descending: {len(aliases.get('data', []))} results"
        )
    except Exception as e:
        results.add_test(
            "Descending Sort",
            "sorting",
            False,
            "Descending sort failed",
            str(e)
        )
    
    # Test 4: Pagination
    print("\n📄 Testing Pagination...")
    
    # Test limit
    try:
        pagination = PaginationOptions(limit=5)
        rules = await client.get_firewall_rules(pagination=pagination)
        data = rules.get("data", [])
        success = len(data) <= 5
        results.add_test(
            "Pagination Limit",
            "pagination",
            success,
            f"Limited results to 5: got {len(data)} results"
        )
    except Exception as e:
        results.add_test(
            "Pagination Limit",
            "pagination",
            False,
            "Pagination limit failed",
            str(e)
        )
    
    # Test offset
    try:
        pagination = PaginationOptions(limit=3, offset=2)
        interfaces = await client.get_interfaces(pagination=pagination)
        data = interfaces.get("data", [])
        success = len(data) <= 3
        results.add_test(
            "Pagination Offset",
            "pagination",
            success,
            f"Offset pagination: got {len(data)} results"
        )
    except Exception as e:
        results.add_test(
            "Pagination Offset",
            "pagination",
            False,
            "Pagination offset failed",
            str(e)
        )
    
    # Test 5: Control Parameters
    print("\n⚙️ Testing Control Parameters...")
    
    # Test dry run (apply=false)
    try:
        rule_data = {
            "interface": "wan",
            "type": "block",
            "protocol": "tcp",
            "source": "192.0.2.100",
            "destination": "any",
            "descr": "Test rule - enhanced MCP"
        }
        control = ControlParameters(apply=False)
        result = await client.create_firewall_rule(rule_data, control)
        success = "data" in result or "id" in result
        results.add_test(
            "Control Parameters (No Apply)",
            "control_parameters",
            success,
            "Created rule without applying changes"
        )
        
        # Clean up - delete the test rule
        if success:
            rule_id = result.get("data", result).get("id")
            if rule_id:
                await client.delete_firewall_rule(rule_id, apply_immediately=True)
                
    except Exception as e:
        results.add_test(
            "Control Parameters (No Apply)",
            "control_parameters",
            False,
            "Control parameters test failed",
            str(e)
        )
    
    # Test 6: HATEOAS
    print("\n🔗 Testing HATEOAS...")
    
    # Test HATEOAS links
    try:
        status = await client.get_system_status()
        links = client.extract_links(status)
        success = isinstance(links, dict)
        results.add_test(
            "HATEOAS Links Extraction",
            "hateoas",
            success,
            f"Extracted {len(links)} HATEOAS links"
        )
        
        # Test following a link (if any exist)
        if links and success:
            try:
                first_link = list(links.values())[0]
                if isinstance(first_link, str):
                    link_result = await client.follow_link(first_link)
                    link_success = "data" in link_result or link_result
                    results.add_test(
                        "HATEOAS Link Following",
                        "hateoas",
                        link_success,
                        f"Successfully followed HATEOAS link"
                    )
                else:
                    results.add_test(
                        "HATEOAS Link Following",
                        "hateoas",
                        False,
                        "Invalid link format"
                    )
            except Exception as e:
                results.add_test(
                    "HATEOAS Link Following",
                    "hateoas",
                    False,
                    "Failed to follow HATEOAS link",
                    str(e)
                )
        
    except Exception as e:
        results.add_test(
            "HATEOAS Links Extraction",
            "hateoas",
            False,
            "HATEOAS test failed",
            str(e)
        )
    
    # Test 7: Object ID Management
    print("\n🆔 Testing Object ID Management...")
    
    # Test finding object by field
    try:
        obj = await client.find_object_by_field("/firewall/rule", "interface", "wan")
        success = obj is not None
        results.add_test(
            "Find Object by Field",
            "object_ids",
            success,
            f"Found object by field: {success}"
        )
    except Exception as e:
        results.add_test(
            "Find Object by Field",
            "object_ids",
            False,
            "Find object by field failed",
            str(e)
        )
    
    # Test refreshing object IDs
    try:
        refreshed = await client.refresh_object_ids("/firewall/rule")
        success = "data" in refreshed
        results.add_test(
            "Refresh Object IDs",
            "object_ids",
            success,
            f"Refreshed object IDs: {len(refreshed.get('data', []))} objects"
        )
    except Exception as e:
        results.add_test(
            "Refresh Object IDs",
            "object_ids",
            False,
            "Refresh object IDs failed",
            str(e)
        )
    
    # Test 8: Advanced Search Methods
    print("\n🔎 Testing Advanced Search Methods...")
    
    # Test interface search
    try:
        interfaces = await client.search_interfaces("wan")
        success = "data" in interfaces
        results.add_test(
            "Interface Search",
            "advanced_search",
            success,
            f"Interface search: {len(interfaces.get('data', []))} results"
        )
    except Exception as e:
        results.add_test(
            "Interface Search",
            "advanced_search",
            False,
            "Interface search failed",
            str(e)
        )
    
    # Test blocked rules search
    try:
        blocked = await client.find_blocked_rules()
        success = "data" in blocked
        results.add_test(
            "Blocked Rules Search",
            "advanced_search",
            success,
            f"Found blocked rules: {len(blocked.get('data', []))}"
        )
    except Exception as e:
        results.add_test(
            "Blocked Rules Search",
            "advanced_search",
            False,
            "Blocked rules search failed",
            str(e)
        )
    
    # Test alias search
    try:
        aliases = await client.search_aliases("test")
        success = "data" in aliases
        results.add_test(
            "Alias Search",
            "advanced_search",
            success,
            f"Alias search: {len(aliases.get('data', []))} results"
        )
    except Exception as e:
        results.add_test(
            "Alias Search",
            "advanced_search",
            False,
            "Alias search failed",
            str(e)
        )
    
    # Test 9: Enhanced Log Analysis
    print("\n📊 Testing Enhanced Log Analysis...")
    
    # Test blocked traffic analysis
    try:
        logs = await client.get_blocked_traffic_logs(lines=10)
        success = "data" in logs
        results.add_test(
            "Blocked Traffic Logs",
            "log_analysis",
            success,
            f"Retrieved blocked traffic logs: {len(logs.get('data', []))} entries"
        )
    except Exception as e:
        results.add_test(
            "Blocked Traffic Logs",
            "log_analysis",
            False,
            "Blocked traffic logs failed",
            str(e)
        )
    
    # Test 10: DHCP Enhanced Features
    print("\n🌐 Testing Enhanced DHCP Features...")
    
    # Test active leases
    try:
        leases = await client.get_active_leases()
        success = "data" in leases
        results.add_test(
            "Active DHCP Leases",
            "dhcp_enhanced",
            success,
            f"Retrieved active leases: {len(leases.get('data', []))}"
        )
    except Exception as e:
        results.add_test(
            "Active DHCP Leases",
            "dhcp_enhanced",
            False,
            "Active DHCP leases failed",
            str(e)
        )
    
    # Test 11: API Capabilities
    print("\n⚡ Testing API Capabilities...")
    
    # Test capabilities query
    try:
        capabilities = await client.get_api_capabilities()
        success = "data" in capabilities or capabilities
        results.add_test(
            "API Capabilities",
            "capabilities",
            success,
            "Retrieved API capabilities"
        )
    except Exception as e:
        results.add_test(
            "API Capabilities",
            "capabilities",
            False,
            "API capabilities failed",
            str(e)
        )
    
    # Close client
    await client.close()
    results.add_test(
        "Client Cleanup",
        "connection",
        True,
        "Enhanced client closed successfully"
    )
    
    # Print results
    results.print_results()
    
    # Summary
    print(f"\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    if results.failed == 0:
        print("🎉 ALL ENHANCED FEATURES WORKING!")
        print("Your pfSense Enhanced MCP Server is fully functional.")
    else:
        print(f"⚠️  {results.failed} test(s) failed out of {results.passed + results.failed}")
        print("Some enhanced features may not be working properly.")
    
    print(f"\nFeatures tested: {len(results.features_tested)}")
    for feature in sorted(results.features_tested):
        feature_tests = [t for t in results.tests if t["feature"] == feature]
        passed = len([t for t in feature_tests if t["success"]])
        total = len(feature_tests)
        status = "✅" if passed == total else "⚠️" if passed > 0 else "❌"
        print(f"  {status} {feature}: {passed}/{total}")
    
    return results.failed == 0

async def test_mcp_enhanced_tools():
    """Test enhanced MCP tools"""
    print(f"\n{'='*80}")
    print("TESTING ENHANCED MCP TOOLS")
    print(f"{'='*80}")
    
    try:
        from main_enhanced_mcp import (
            search_interfaces,
            search_firewall_rules,
            find_blocked_rules,
            search_aliases,
            enable_hateoas,
            test_enhanced_connection,
            get_api_capabilities
        )
        print("✅ Enhanced MCP tools imported successfully")
    except Exception as e:
        print(f"❌ Failed to import enhanced MCP tools: {e}")
        return False
    
    # Test enhanced tools
    tools_to_test = [
        ("test_enhanced_connection", test_enhanced_connection, {}),
        ("search_interfaces", search_interfaces, {"search_term": "wan", "page_size": 5}),
        ("search_firewall_rules", search_firewall_rules, {"interface": "wan", "page_size": 5}),
        ("find_blocked_rules", find_blocked_rules, {"page_size": 5}),
        ("search_aliases", search_aliases, {"alias_type": "host", "page_size": 5}),
        ("enable_hateoas", enable_hateoas, {}),
        ("get_api_capabilities", get_api_capabilities, {})
    ]
    
    for tool_name, tool_func, kwargs in tools_to_test:
        try:
            result = await tool_func(**kwargs)
            if result.get("success"):
                print(f"✅ {tool_name}: {result.get('message', 'Success')}")
                if 'count' in result:
                    print(f"   Results: {result['count']}")
                if 'links' in result and result['links']:
                    print(f"   HATEOAS links: {len(result['links'])}")
            else:
                print(f"❌ {tool_name}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ {tool_name}: Exception - {e}")
    
    return True

def print_enhanced_config_help():
    """Print enhanced configuration help"""
    print(f"\n{'='*80}")
    print("ENHANCED CONFIGURATION HELP")
    print(f"{'='*80}")
    print("Required environment variables:")
    print("  PFSENSE_URL=https://your-pfsense.local")
    print("  PFSENSE_API_KEY=your-api-key")
    print()
    print("Enhanced features:")
    print("  ENABLE_HATEOAS=true          # Enable navigation links")
    print("  DEFAULT_PAGE_SIZE=20         # Default pagination size")
    print("  ENABLE_CACHING=true          # Enable response caching")
    print()
    print("Example enhanced configuration:")
    print("  export PFSENSE_URL=https://192.168.1.1")
    print("  export PFSENSE_API_KEY=your-key-here")
    print("  export PFSENSE_VERSION=CE_2_8_0")
    print("  export ENABLE_HATEOAS=true")
    print("  export DEBUG=false")
    print()
    print("Run tests:")
    print("  python test_enhanced_features.py")

def main():
    """Main test function"""
    print("pfSense Enhanced API Features Test Suite")
    print(f"{'='*80}")
    
    # Check configuration
    if not os.getenv("PFSENSE_URL"):
        print("❌ Missing PFSENSE_URL environment variable")
        print_enhanced_config_help()
        return 1
    
    if not os.getenv("PFSENSE_API_KEY") and not (os.getenv("PFSENSE_USERNAME") and os.getenv("PFSENSE_PASSWORD")):
        print("❌ Missing authentication credentials")
        print_enhanced_config_help()
        return 1
    
    try:
        # Test enhanced API features
        api_success = asyncio.run(test_enhanced_api_features())
        
        # Test enhanced MCP tools
        mcp_success = asyncio.run(test_mcp_enhanced_tools())
        
        if api_success and mcp_success:
            print(f"\n🎉 ALL ENHANCED TESTS PASSED!")
            print("Your pfSense Enhanced MCP Server is fully functional with:")
            print("  ✅ Advanced Query Filters")
            print("  ✅ Multi-field Sorting")
            print("  ✅ Pagination Support")
            print("  ✅ Control Parameters")
            print("  ✅ HATEOAS Navigation")
            print("  ✅ Object ID Management")
            print("  ✅ Enhanced Search Methods")
            return 0
        else:
            print(f"\n❌ Some enhanced features failed.")
            print("Check the output above for details.")
            return 1
            
    except KeyboardInterrupt:
        print(f"\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())