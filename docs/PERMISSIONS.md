# pfSense MCP Server - Permissions Guide

## Overview

The pfSense MCP Server implements a hierarchical permission model with 5 access levels, as defined in the original scope of work (SOW).

## Access Levels

### 1. READ_ONLY (Level 0)
**Purpose**: Basic monitoring and viewing capabilities
**Typical Users**: Security Analysts, NOC Staff, Auditors

**Allowed Operations**:
- View system status and health
- List network interfaces
- View firewall rules
- Show blocked IPs
- Analyze threats
- View logs
- Monitor VPN status
- Check service status

**Example Commands**:
```
"Show me the system status"
"What IPs are currently blocked?"
"List all firewall rules"
"Show me today's security events"
```

### 2. COMPLIANCE_READ (Level 1)
**Purpose**: Compliance checking and audit functions
**Typical Users**: Compliance Officers, Internal Auditors

**Includes**: All READ_ONLY permissions plus:
- Run compliance scans (PCI-DSS, HIPAA, SOC2, etc.)
- Generate audit reports
- Check security baselines
- Export compliance data
- View configuration history
- Access detailed audit logs

**Example Commands**:
```
"Run a PCI compliance check"
"Generate HIPAA compliance report"
"Show me all configuration changes this month"
"Check our security baseline status"
```

### 3. SECURITY_WRITE (Level 2)
**Purpose**: Security operations and rule management
**Typical Users**: Security Engineers, SOC Analysts

**Includes**: All COMPLIANCE_READ permissions plus:
- Create/modify/delete firewall rules
- Block/unblock IP addresses
- Update threat feeds
- Configure security policies
- Manage VPN users
- Update IDS/IPS rules

**Example Commands**:
```
"Block IP 192.168.1.100"
"Create a rule to allow HTTPS to web server"
"Update the GeoIP block list"
"Enable IDS for the DMZ"
```

### 4. ADMIN_WRITE (Level 3)
**Purpose**: Full system administration
**Typical Users**: System Administrators, Senior Engineers

**Includes**: All SECURITY_WRITE permissions plus:
- Configure network interfaces
- Manage system settings
- User management
- Backup and restore
- Package management
- System updates
- Advanced configurations

**Example Commands**:
```
"Configure VLAN 100 on interface em1"
"Create a new admin user"
"Backup the current configuration"
"Update pfSense to latest version"
```

### 5. EMERGENCY_WRITE (Level 4)
**Purpose**: Emergency response and critical operations
**Typical Users**: Incident Response Team, Security Managers

**Includes**: All permissions plus:
- Emergency block all
- Activate incident mode
- Network isolation
- Emergency restore
- Override safety checks
- Panic mode activation
- Critical system recovery

**Example Commands**:
```
"EMERGENCY: Block all traffic from China"
"Activate incident response mode"
"Isolate the compromised VLAN immediately"
"Emergency restore to last known good configuration"
```

## Permission Configuration

### Setting Default Access Level

In `.env` file:
```bash
DEFAULT_ACCESS_LEVEL=READ_ONLY
```

### User-Specific Access

Generate tokens with specific access levels:
```bash
# Read-only token for analyst
python scripts/generate_token.py alice READ_ONLY

# Security write token for engineer
python scripts/generate_token.py bob SECURITY_WRITE

# Emergency token for incident response
python scripts/generate_token.py carol EMERGENCY_WRITE
```

### Claude Desktop Configuration

Set access level in Claude Desktop config:
```json
{
  "mcpServers": {
    "pfsense": {
      "command": "python",
      "args": ["main.py"],
      "env": {
        "DEFAULT_ACCESS_LEVEL": "SECURITY_WRITE"
      }
    }
  }
}
```

## Permission Checks

### How Permission Checks Work

1. **Hierarchical Model**: Higher levels include all lower level permissions
2. **Explicit Checks**: Each tool validates required permission
3. **Audit Logging**: All operations logged with user context
4. **Fail Safe**: Default to most restrictive if uncertain

### Example Implementation

```python
# Tool checks permission before execution
async def block_ip(params: Dict, context: SecurityContext):
    # Requires SECURITY_WRITE or higher
    if not PermissionManager.check_permission(
        context.access_level, 
        AccessLevel.SECURITY_WRITE
    ):
        raise PermissionError("Insufficient permissions")
    
    # Proceed with operation...
```

## Best Practices

### 1. Principle of Least Privilege
- Start users with READ_ONLY
- Elevate only as needed
- Regular access reviews
- Time-bound elevated access

### 2. Separation of Duties
- Compliance officers can't modify rules
- Engineers can't approve their own changes
- Emergency access requires justification

### 3. Audit Trail
- All operations logged
- User attribution
- Timestamp and context
- Immutable audit log

### 4. Emergency Procedures
- Break-glass access for emergencies
- Automatic alerts on emergency use
- Post-incident review required
- Time-limited emergency access

## Access Control Matrix

| Operation | READ_ONLY | COMPLIANCE_READ | SECURITY_WRITE | ADMIN_WRITE | EMERGENCY_WRITE |
|-----------|-----------|-----------------|----------------|-------------|-----------------|
| View Status | ✅ | ✅ | ✅ | ✅ | ✅ |
| View Rules | ✅ | ✅ | ✅ | ✅ | ✅ |
| Run Compliance | ❌ | ✅ | ✅ | ✅ | ✅ |
| Block IP | ❌ | ❌ | ✅ | ✅ | ✅ |
| System Config | ❌ | ❌ | ❌ | ✅ | ✅ |
| Emergency Block | ❌ | ❌ | ❌ | ❌ | ✅ |

## Token Management

### Token Format
```json
{
  "user_id": "alice",
  "access_level": "READ_ONLY",
  "issued": "2024-01-20T10:00:00Z",
  "expires": "2024-02-19T10:00:00Z",
  "token_id": "unique-id"
}
```

### Token Rotation
- Regular rotation (30-90 days)
- Immediate revocation capability
- Audit token usage
- Monitor for anomalies

## Compliance Requirements

### PCI-DSS
- Unique user IDs ✅
- Role-based access ✅
- Access logging ✅
- Regular reviews ✅

### HIPAA
- Minimum necessary access ✅
- User authentication ✅
- Audit controls ✅
- Access termination ✅

### SOC2
- Logical access controls ✅
- Segregation of duties ✅
- Access monitoring ✅
- Change management ✅

## Troubleshooting

### Common Permission Issues

1. **"Insufficient permissions" error**
   - Check user's access level
   - Verify token is valid
   - Review required level for operation

2. **Operation succeeded but shouldn't have**
   - Check permission hierarchy
   - Review audit logs
   - Verify permission checks in code

3. **Can't access compliance tools**
   - Need COMPLIANCE_READ or higher
   - Check DEFAULT_ACCESS_LEVEL
   - Verify token generation

### Permission Debugging

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
# Check logs for permission checks
tail -f /var/log/pfsense-mcp/server.log | grep -i permission
```

## Security Notes

1. **Never share tokens** between users
2. **Use environment variables** for sensitive data
3. **Enable audit logging** always
4. **Review access quarterly**
5. **Document emergency access** usage
6. **Implement alerting** for privilege escalation
