# MCP Tools Reference

Complete reference for all 25+ Enhanced MCP Tools available in the pfSense Enhanced MCP Server.

## 🏷️ Tool Categories

- [🔍 Search & Discovery](#-search--discovery)
- [🛡️ Firewall Management](#️-firewall-management)
- [📊 Monitoring & Logs](#-monitoring--logs)
- [🌐 DHCP Management](#-dhcp-management)
- [🔗 HATEOAS Navigation](#-hateoas-navigation)
- [🆔 Object Management](#-object-management)
- [⚙️ System Tools](#️-system-tools)
- [🔧 Utility Tools](#-utility-tools)

---

## 🔍 Search & Discovery

### `search_interfaces()`

Search and filter network interfaces with advanced options.

**Parameters:**
- `search_term` (str, optional): Search in interface names/descriptions
- `status_filter` (str, optional): Filter by status (up, down, etc.)
- `page` (int): Page number for pagination (default: 1)
- `page_size` (int): Number of results per page (default: 20)
- `sort_by` (str): Field to sort by (default: "name")

**Example:**
```python
# Find all WAN interfaces that are currently up
result = await search_interfaces(
    search_term="wan", 
    status_filter="up",
    page_size=10
)
```

**Response:**
```json
{
  "success": true,
  "page": 1,
  "page_size": 10,
  "total_results": 3,
  "interfaces": [...],
  "links": {...},
  "timestamp": "2025-01-19T..."
}
```

### `search_firewall_rules()`

Search firewall rules with comprehensive filtering and pagination.

**Parameters:**
- `interface` (str, optional): Filter by interface (wan, lan, etc.)
- `source_ip` (str, optional): Filter by source IP (supports partial matching)
- `destination_port` (int/str, optional): Filter by destination port
- `rule_type` (str, optional): Filter by rule type (pass, block, reject)
- `search_description` (str, optional): Search in rule descriptions
- `page` (int): Page number (default: 1)
- `page_size` (int): Results per page (default: 20)
- `sort_by` (str): Sort field (default: "sequence")

**Example:**
```python
# Find all blocking rules on WAN for SSH traffic
result = await search_firewall_rules(
    interface="wan",
    destination_port=22,
    rule_type="block",
    page_size=5
)
```

### `search_aliases()`

Search aliases with intelligent filtering options.

**Parameters:**
- `search_term` (str, optional): Search in alias names or descriptions
- `alias_type` (str, optional): Filter by type (host, network, port, url)
- `containing_ip` (str, optional): Find aliases containing this IP
- `page` (int): Page number (default: 1)
- `page_size` (int): Results per page (default: 20)
- `sort_by` (str): Sort field (default: "name")

**Example:**
```python
# Find all host aliases containing a specific IP
result = await search_aliases(
    alias_type="host",
    containing_ip="192.168.1.100"
)
```

### `search_dhcp_leases()`

Search DHCP leases with advanced filtering.

**Parameters:**
- `search_term` (str, optional): General search for hostname or IP
- `interface` (str, optional): Filter by interface
- `mac_address` (str, optional): Filter by MAC address
- `hostname` (str, optional): Filter by hostname (partial matching)
- `state` (str): Filter by lease state (default: "active")
- `page` (int): Page number (default: 1)
- `page_size` (int): Results per page (default: 20)
- `sort_by` (str): Sort field (default: "start")

**Example:**
```python
# Find active leases for hostnames containing "server"
result = await search_dhcp_leases(
    hostname="server",
    state="active",
    page_size=15
)
```

---

## 🛡️ Firewall Management

### `create_firewall_rule_advanced()`

Create firewall rules with advanced placement and control options.

**Parameters:**
- `interface` (str): Interface for the rule (wan, lan, etc.)
- `rule_type` (str): Rule type (pass, block, reject)
- `protocol` (str): Protocol (tcp, udp, icmp, any)
- `source` (str): Source address (any, IP, network, alias)
- `destination` (str): Destination address
- `description` (str, optional): Rule description
- `destination_port` (str, optional): Destination port or range
- `position` (int, optional): Position to insert rule (0 = top)
- `apply_immediately` (bool): Apply changes immediately (default: True)
- `log_matches` (bool): Log rule matches (default: True)

**Example:**
```python
# Create a blocking rule at the top of the WAN rules
result = await create_firewall_rule_advanced(
    interface="wan",
    rule_type="block",
    protocol="tcp",
    source="198.51.100.0/24",
    destination="any",
    description="Block suspicious network",
    position=0,
    apply_immediately=True
)
```

### `move_firewall_rule()`

Move a firewall rule to a new position in the rule order.

**Parameters:**
- `rule_id` (int): ID of the rule to move
- `new_position` (int): New position (0 = top)
- `apply_immediately` (bool): Apply changes immediately (default: True)

**Example:**
```python
# Move rule to top priority
result = await move_firewall_rule(
    rule_id=15,
    new_position=0,
    apply_immediately=True
)
```

### `bulk_block_ips()`

Block multiple IP addresses efficiently in one operation.

**Parameters:**
- `ip_addresses` (list): List of IP addresses to block
- `interface` (str): Interface to apply blocks (default: "wan")
- `description_prefix` (str): Prefix for rule descriptions

**Example:**
```python
# Block multiple malicious IPs
result = await bulk_block_ips(
    ip_addresses=[
        "198.51.100.1",
        "203.0.113.1", 
        "192.0.2.1"
    ],
    interface="wan",
    description_prefix="Threat intel block"
)
```

### `find_blocked_rules()`

Find all firewall rules that block or reject traffic.

**Parameters:**
- `interface` (str, optional): Filter by interface
- `page` (int): Page number (default: 1)
- `page_size` (int): Results per page (default: 20)

**Example:**
```python
# Find all blocking rules on WAN
result = await find_blocked_rules(interface="wan")
```

### `manage_alias_addresses()`

Add or remove addresses from an existing alias.

**Parameters:**
- `alias_id` (int): ID of the alias to modify
- `action` (str): Action to perform ('add' or 'remove')
- `addresses` (list): List of addresses to add or remove

**Example:**
```python
# Add new IPs to existing blocklist alias
result = await manage_alias_addresses(
    alias_id=5,
    action="add",
    addresses=["192.0.2.100", "192.0.2.101"]
)
```

---

## 📊 Monitoring & Logs

### `analyze_blocked_traffic()`

Analyze blocked traffic patterns from firewall logs.

**Parameters:**
- `hours_back` (int): How many hours back to analyze (default: 24)
- `limit` (int): Maximum log entries to analyze (default: 100)
- `group_by_source` (bool): Group results by source IP (default: True)

**Example:**
```python
# Analyze last 24 hours of blocked traffic
result = await analyze_blocked_traffic(
    hours_back=24,
    limit=1000,
    group_by_source=True
)
```

**Response includes:**
- Top blocking sources with threat scores
- Port scan detection
- Attack pattern analysis
- Time-based statistics

### `search_logs_by_ip()`

Search logs for activity related to a specific IP address.

**Parameters:**
- `ip_address` (str): IP address to search for
- `log_type` (str): Type of logs (default: "firewall")
- `lines` (int): Number of log lines (default: 100)
- `include_related` (bool): Include related traffic (default: True)

**Example:**
```python
# Get all firewall activity for suspicious IP
result = await search_logs_by_ip(
    ip_address="198.51.100.1",
    log_type="firewall",
    lines=200
)
```

### `get_firewall_logs()`

Get recent firewall logs with filtering options.

**Parameters:**
- `lines` (int): Number of log lines (default: 50)

**Example:**
```python
# Get recent firewall activity
result = await get_firewall_logs(lines=100)
```

---

## 🌐 DHCP Management

### `find_interfaces_by_status()`

Find interfaces by their current operational status.

**Parameters:**
- `status` (str): Interface status to filter by (up, down, etc.)

**Example:**
```python
# Find all down interfaces
result = await find_interfaces_by_status("down")
```

---

## 🔗 HATEOAS Navigation

### `enable_hateoas()`

Enable HATEOAS links in API responses for this session.

**Parameters:** None

**Example:**
```python
# Enable navigation links
result = await enable_hateoas()
```

### `disable_hateoas()`

Disable HATEOAS links in API responses for this session.

**Parameters:** None

**Example:**
```python
# Disable navigation links for compact responses
result = await disable_hateoas()
```

### `follow_api_link()`

Follow a HATEOAS link from a previous API response.

**Parameters:**
- `link_url` (str): The link URL to follow (from _links section)

**Example:**
```python
# Follow a next page link
result = await follow_api_link("/api/v2/firewall/rule?page=2")
```

---

## 🆔 Object Management

### `refresh_object_ids()`

Refresh object IDs by re-querying an endpoint (handles ID changes).

**Parameters:**
- `endpoint` (str): API endpoint to refresh (e.g., '/firewall/rule')

**Example:**
```python
# Refresh firewall rule IDs after deletions
result = await refresh_object_ids("/firewall/rule")
```

### `find_object_by_field()`

Find an object by a specific field value (safer than using IDs).

**Parameters:**
- `endpoint` (str): API endpoint to search
- `field` (str): Field name to search by
- `value` (str): Value to search for

**Example:**
```python
# Find rule by description instead of unreliable ID
result = await find_object_by_field(
    endpoint="/firewall/rule",
    field="descr",
    value="Block malware traffic"
)
```

---

## ⚙️ System Tools

### `system_status()`

Get current system status including CPU, memory, disk usage.

**Parameters:** None

**Example:**
```python
# Get comprehensive system status
result = await system_status()
```

### `get_api_capabilities()`

Get comprehensive API capabilities and configuration.

**Parameters:** None

**Example:**
```python
# Discover what the API can do
result = await get_api_capabilities()
```

### `test_enhanced_connection()`

Test enhanced API connection with feature validation.

**Parameters:** None

**Example:**
```python
# Test all enhanced features
result = await test_enhanced_connection()
```

**Response includes:**
- Basic connectivity test
- Feature availability (filtering, sorting, HATEOAS)
- Performance metrics
- Capability summary

---

## 🔧 Utility Tools

### `list_interfaces()`

List all network interfaces with their status and configuration.

**Parameters:** None

**Example:**
```python
# Get all interfaces
result = await list_interfaces()
```

### `get_interface_details()`

Get detailed information about a specific network interface.

**Parameters:**
- `interface_id` (str): Interface identifier (wan, lan, opt1, etc.)

**Example:**
```python
# Get WAN interface details
result = await get_interface_details("wan")
```

### `list_services()`

List all services and their current status.

**Parameters:** None

**Example:**
```python
# Get service status overview
result = await list_services()
```

### `restart_service()`

Restart a specific service.

**Parameters:**
- `service_name` (str): Name of the service to restart

**Example:**
```python
# Restart DNS resolver
result = await restart_service("unbound")
```

### `list_config_backups()`

List available configuration backups.

**Parameters:** None

**Example:**
```python
# See available backups
result = await list_config_backups()
```

### `create_config_backup()`

Create a configuration backup with description.

**Parameters:**
- `description` (str): Description for the backup

**Example:**
```python
# Create backup before changes
result = await create_config_backup("Before firewall rule changes")
```

---

## 🎯 Tool Selection Guide

### For Network Discovery
- `search_interfaces()` - Find specific interfaces
- `search_dhcp_leases()` - Discover network devices
- `get_arp_table()` - See active connections

### For Security Operations  
- `search_firewall_rules()` - Find existing rules
- `analyze_blocked_traffic()` - Threat analysis
- `bulk_block_ips()` - Rapid threat response
- `find_blocked_rules()` - Security audit

### For Maintenance
- `list_services()` - Check service health
- `system_status()` - Monitor resources
- `create_config_backup()` - Before changes
- `test_enhanced_connection()` - Validate setup

### For Automation
- `create_firewall_rule_advanced()` - Precise rule creation
- `move_firewall_rule()` - Rule prioritization
- `manage_alias_addresses()` - Dynamic lists
- `refresh_object_ids()` - Handle ID changes

---

## 🔄 Response Format

All enhanced MCP tools return a consistent response format:

```json
{
  "success": true|false,
  "message": "Human readable message",
  "data": {...},           // Main response data
  "count": 0,              // Number of items (if applicable)
  "page": 1,               // Current page (if paginated)
  "page_size": 20,         // Page size (if paginated)
  "links": {...},          // HATEOAS links (if enabled)
  "timestamp": "2025-01-19T...",
  "error": "Error message" // Only present if success=false
}
```

## 🚀 Performance Tips

### Efficient Queries
- Use specific filters to reduce data transfer
- Choose appropriate page sizes (20-50 items)
- Sort by indexed fields when possible

### Bulk Operations  
- Use `bulk_block_ips()` instead of individual blocks
- Combine related changes before applying
- Leverage control parameters for efficiency

### Caching Strategy
- Read-only operations are automatically cached
- Use `refresh_object_ids()` after bulk changes
- Monitor cache hit rates for optimization

---

For more information, see:
- [Enhanced Features Guide](ENHANCED_FEATURES.md)
- [Configuration Reference](CONFIGURATION.md)
- [API Integration Details](API_INTEGRATION.md)