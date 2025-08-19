# Enhanced Features Guide

This guide covers all the advanced features available in the pfSense Enhanced MCP Server v4.0.0.

## 🎯 Overview

The Enhanced MCP Server builds upon the [jaredhendrickson13/pfsense-api](https://github.com/jaredhendrickson13/pfsense-api) v2 package to provide sophisticated automation capabilities that go far beyond basic pfSense management.

## 🔍 Advanced Filtering

### Filter Types

The enhanced server supports 8 different filter operators:

| Operator | Description | Example |
|----------|-------------|---------|
| `exact` | Exact match (default) | `interface=wan` |
| `contains` | Substring match | `description__contains=malware` |
| `startswith` | String starts with | `name__startswith=VLAN` |
| `endswith` | String ends with | `interface__endswith=_MGMT` |
| `lt` | Less than | `port__lt=1024` |
| `lte` | Less than or equal | `priority__lte=10` |
| `gt` | Greater than | `size__gt=100` |
| `gte` | Greater than or equal | `timestamp__gte=2025-01-01` |
| `regex` | Regular expression | `type__regex=block\|reject` |

### Multi-Field Filtering

Combine multiple filters for precise results:

```python
# Find WAN firewall rules blocking high ports
filters = [
    QueryFilter("interface", "wan"),
    QueryFilter("type", "block"),
    QueryFilter("destination_port", "1024", "gt")
]
```

### Practical Examples

```python
# Search for interfaces with "wan" in the name that are currently up
search_interfaces(search_term="wan", status_filter="up")

# Find firewall rules containing "malware" in description
search_firewall_rules(search_description="malware")

# Locate DHCP leases for hostnames starting with "server"
search_dhcp_leases(hostname="server", state="active")
```

## 📊 Smart Pagination & Sorting

### Pagination

Handle large datasets efficiently with page-based navigation:

```python
# Get page 2 with 20 results per page
search_firewall_rules(page=2, page_size=20)

# Equivalent low-level pagination
pagination = PaginationOptions(limit=20, offset=20)
```

### Sorting Options

Sort results by any field in ascending or descending order:

```python
# Sort firewall rules by priority (sequence)
search_firewall_rules(sort_by="sequence", interface="wan")

# Sort interfaces by name (descending)
search_interfaces(sort_by="name", page_size=10)

# Low-level sorting control
sort = SortOptions(sort_by="timestamp", sort_order="desc", reverse=False)
```

### Performance Benefits

- **Reduced Memory Usage**: Only load needed data
- **Faster Response Times**: Smaller payloads
- **Better User Experience**: Progressive data loading
- **Network Efficiency**: Reduced bandwidth consumption

## 🔗 HATEOAS Navigation

### What is HATEOAS?

HATEOAS (Hypermedia as the Engine of Application State) provides dynamic API navigation through embedded links in responses.

### Enabling HATEOAS

```bash
# Enable in environment
export ENABLE_HATEOAS=true

# Or enable programmatically
enable_hateoas()
```

### Using Navigation Links

```python
# Get system status with navigation links
result = await system_status()
links = result.get("links", {})

# Available link types
{
    "self": "/api/v2/status/system",
    "update": "/api/v2/system/config",
    "next": "/api/v2/status/interfaces",
    "pfsense:firewall": "/api/v2/firewall/rule"
}

# Follow a link dynamically
next_data = await follow_api_link(links["next"])
```

### Benefits

- **API Discovery**: Discover available endpoints dynamically
- **Version Independence**: Links adapt to API changes
- **Reduced Hardcoding**: No need to hardcode endpoint URLs
- **Better Integration**: Self-documenting API relationships

## ⚙️ Control Parameters

### Available Parameters

Control exactly how operations are performed:

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `apply` | Boolean | Apply changes immediately | `false` |
| `async` | Boolean | Execute asynchronously | `true` |
| `placement` | Integer | Position for new objects | `null` |
| `append` | Boolean | Add to existing arrays | `false` |
| `remove` | Boolean | Remove from arrays | `false` |

### Examples

```python
# Create firewall rule at top of list and apply immediately
create_firewall_rule_advanced(
    interface="wan",
    rule_type="block",
    protocol="tcp",
    source="198.51.100.0/24",
    destination="any",
    position=0,           # Top of list
    apply_immediately=True
)

# Add IPs to existing alias without replacing
manage_alias_addresses(
    alias_id=5,
    action="add",
    addresses=["192.0.2.100", "192.0.2.101"]
)

# Move firewall rule to specific position
move_firewall_rule(
    rule_id=10,
    new_position=2,
    apply_immediately=True
)
```

### Bulk Operations

Perform multiple operations efficiently:

```python
# Block multiple IPs in one operation
bulk_block_ips([
    "198.51.100.1",
    "203.0.113.1", 
    "192.0.2.1"
], interface="wan")
```

## 🆔 Object ID Management

### The Challenge

pfSense object IDs are **dynamic** and **non-persistent**:
- IDs change when objects are deleted or reordered
- Hardcoded IDs become invalid over time
- Array-based indexing causes ID shifts

### Solutions

#### 1. Field-Based Lookups

Find objects by unique field values instead of IDs:

```python
# Find rule by description instead of ID
rule = await find_object_by_field(
    endpoint="/firewall/rule",
    field="descr", 
    value="Block malware traffic"
)
```

#### 2. ID Refresh

Update your object ID cache:

```python
# Refresh firewall rule IDs after changes
refreshed_rules = await refresh_object_ids("/firewall/rule")
current_ids = {rule["descr"]: rule["id"] for rule in refreshed_rules["data"]}
```

#### 3. Immediate Operations

Use control parameters to avoid ID issues:

```python
# Create and apply in one operation
create_firewall_rule_advanced(
    # rule parameters
    apply_immediately=True  # No need to track ID for later apply
)
```

## 📈 Performance Optimization

### Caching Strategy

The enhanced client implements intelligent caching:

```python
# Automatic caching for read operations
interfaces = await get_interfaces()  # Cached for 5 minutes
interfaces = await get_interfaces()  # Returns cached result

# Bypass cache when needed
status = await get_system_status()  # Always fresh for status
```

### Connection Pooling

Efficient HTTP connection management:
- **Persistent Connections**: Reuse TCP connections
- **Connection Limits**: Prevent resource exhaustion
- **Timeout Handling**: Graceful failure recovery

### Async Operations

Non-blocking I/O for better performance:
- **Concurrent Requests**: Multiple operations in parallel
- **Resource Efficiency**: Better CPU and memory usage
- **Scalability**: Handle more simultaneous users

## 🔧 Advanced Search Methods

### Interface Search

```python
# Find all WAN-related interfaces
wan_interfaces = await search_interfaces(search_term="wan")

# Find interfaces by status
down_interfaces = await find_interfaces_by_status("down")
```

### Firewall Rule Search

```python
# Complex firewall rule search
rules = await search_firewall_rules(
    interface="wan",
    source_ip="192.168",      # Partial IP match
    rule_type="block",
    search_description="malware",
    page=1,
    page_size=20,
    sort_by="sequence"
)
```

### Alias Discovery

```python
# Find aliases containing specific IP
aliases_with_ip = await search_aliases(containing_ip="10.0.0.1")

# Search by alias type
host_aliases = await search_aliases(alias_type="host")
```

### Log Analysis

```python
# Analyze blocked traffic patterns
analysis = await analyze_blocked_traffic(
    hours_back=24,
    limit=1000,
    group_by_source=True
)

# Search logs for specific IP
ip_logs = await search_logs_by_ip(
    ip_address="192.0.2.1",
    log_type="firewall", 
    lines=100
)
```

## 🛡️ Enhanced Security Features

### Input Validation

All user inputs are validated and sanitized:
- **Type Checking**: Ensure correct data types
- **Range Validation**: Check numeric ranges
- **Format Validation**: Validate IP addresses, hostnames
- **Injection Prevention**: Prevent command injection

### Privilege Checking

Operations respect pfSense privilege system:
- **Endpoint Privileges**: Each API endpoint has specific privileges
- **User Validation**: Check user has required privileges
- **Operation Logging**: Track all privileged operations

### Audit Trail

Comprehensive logging of all operations:
- **User Actions**: Who performed what action
- **Timestamps**: When operations occurred
- **Success/Failure**: Operation outcomes
- **Change Tracking**: What was modified

## 🔄 Migration from Basic MCP

### Configuration Updates

Update your environment configuration:

```bash
# Old basic configuration
PFSENSE_CONNECTION_METHOD=xmlrpc
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=password

# New enhanced configuration  
AUTH_METHOD=api_key
PFSENSE_API_KEY=your-api-key
ENABLE_HATEOAS=false
DEFAULT_PAGE_SIZE=20
```

### Tool Updates

Enhanced tools provide backward compatibility:

```python
# Old: Basic rule listing
list_firewall_rules()

# New: Enhanced with filtering
search_firewall_rules(interface="wan", page_size=10)

# Old: Simple IP blocking  
block_ip_address("192.0.2.1")

# New: Bulk operations
bulk_block_ips(["192.0.2.1", "192.0.2.2"])
```

### Feature Adoption

Gradually adopt enhanced features:

1. **Start with Basic**: Use enhanced tools with default parameters
2. **Add Filtering**: Implement search and filtering
3. **Enable Pagination**: Handle large datasets
4. **Use HATEOAS**: Dynamic API navigation
5. **Implement Caching**: Optimize performance

## 🎯 Best Practices

### Efficient Filtering

- **Use Specific Filters**: Narrow down results early
- **Combine Filters**: Use multiple criteria together
- **Choose Right Operators**: Use appropriate filter types

### Pagination Strategy

- **Reasonable Page Sizes**: 20-50 items per page
- **Progress Indicators**: Show pagination status
- **Deep Pagination**: Be aware of performance impact

### Error Handling

- **Graceful Degradation**: Handle API failures gracefully
- **Retry Logic**: Implement exponential backoff
- **User Feedback**: Provide meaningful error messages

### Performance Optimization

- **Cache Appropriately**: Cache read-only data
- **Batch Operations**: Combine multiple changes
- **Monitor Performance**: Track response times

## 🔮 Future Enhancements

### Planned Features

- **GraphQL Support**: More flexible queries
- **Real-time Updates**: WebSocket notifications
- **Advanced Analytics**: Machine learning insights
- **Multi-Instance**: Manage multiple pfSense systems

### Community Contributions

Help us improve the enhanced features:
- **Test Edge Cases**: Try unusual configurations
- **Report Bugs**: Help us fix issues
- **Suggest Features**: Share your ideas
- **Contribute Code**: Submit pull requests

---

For more information, see:
- [API Integration Details](API_INTEGRATION.md)
- [MCP Tools Reference](MCP_TOOLS.md)
- [Configuration Reference](CONFIGURATION.md)