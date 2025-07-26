# pfSense MCP Server - Simplified FastMCP Implementation

A focused, lightweight implementation of pfSense management via Model Context Protocol using FastMCP framework.

## Features

### Core Functionality
- **FastMCP Framework**: Clean, pythonic implementation of MCP protocol
- **Multi-Edition Support**: Compatible with pfSense CE 2.8.0+ and Plus 24.11+
- **Multiple Connection Methods**: REST API, XML-RPC, and SSH
- **Essential Tools**: Firewall management, system monitoring, service control
- **Docker Ready**: Fully containerized for easy deployment

### pfSense Edition Differences
- **CE (Community Edition)**: Uses API key + secret authentication
- **Plus (Commercial)**: Uses Bearer token authentication with API v2

## Quick Start

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/yourusername/pfsense-mcp-server.git
cd pfsense-mcp-server

# Create environment file
cp .env.example .env
# Edit .env with your pfSense details
```

### 2. Essential Configuration

```env
# pfSense Connection
PFSENSE_URL=https://your-pfsense.example.com
PFSENSE_VERSION=ce               # or "plus"
PFSENSE_CONNECTION_METHOD=rest   # or "xmlrpc" or "ssh"

# For REST API (recommended)
PFSENSE_API_KEY=your-api-key
PFSENSE_API_SECRET=your-secret   # CE only

# For XML-RPC (legacy)
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password

# For SSH (advanced)
PFSENSE_SSH_HOST=your-pfsense.example.com
PFSENSE_SSH_USERNAME=admin
SSH_KEY_FILE=./config/ssh/id_rsa
```

### 3. Run with Docker

```bash
# Using simplified Docker Compose
docker-compose -f docker-compose-simple.yml up -d

# Or build and run directly
docker build -f Dockerfile.simple -t pfsense-mcp:simple .
docker run -d --env-file .env -p 8000:8000 pfsense-mcp:simple
```

### 4. For Claude Desktop

```bash
# Run in stdio mode
docker run -it --rm --env-file .env pfsense-mcp:simple --stdio

# Or without Docker
pip install -r requirements-simple.txt
python main_fastmcp.py --stdio
```

## Available Tools

### System Management
- `system_status()` - Get system health and resource usage
- `list_interfaces()` - List network interfaces
- `get_service_status()` - Check service status
- `restart_service()` - Restart services
- `backup_config()` - Create configuration backup

### Firewall Management
- `get_firewall_rules()` - View firewall rules
- `create_firewall_rule()` - Create new rules
- `block_ip_address()` - Quick IP blocking

### Network Monitoring
- `get_dhcp_leases()` - View DHCP leases
- `get_arp_table()` - Check ARP entries
- `get_vpn_status()` - Monitor VPN connections

## Examples

### Python Usage

```python
from fastmcp import FastMCP
import asyncio

# Initialize client
client = FastMCP("http://localhost:8000")

# Get system status
status = await client.call_tool("system_status")
print(f"CPU Usage: {status['cpu_usage']}%")

# Block an IP
result = await client.call_tool("block_ip_address", {
    "ip_address": "192.168.1.100",
    "reason": "Suspicious activity"
})

# Create firewall rule
rule = await client.call_tool("create_firewall_rule", {
    "interface": "wan",
    "action": "pass",
    "protocol": "tcp",
    "destination_port": "443",
    "description": "Allow HTTPS"
})
```

### MCP Resources

Access pfSense data directly via resources:

```
pfsense://system/info      - System information
pfsense://interfaces/all   - All interfaces
pfsense://firewall/rules   - Firewall rules
```

## Connection Methods

### REST API (Recommended)
- Fastest and most feature-complete
- Different auth for CE vs Plus
- Requires API package installed on pfSense

### XML-RPC (Legacy)
- Works with older pfSense versions
- Username/password authentication
- Limited functionality

### SSH (Advanced)
- Direct command execution
- Requires SSH access
- Most powerful but slower

## Minimal Requirements

- Docker 20.10+ OR Python 3.8+
- Network access to pfSense
- Valid credentials for chosen connection method
- 512MB RAM, 1 CPU core

## Security Notes

1. **Use HTTPS**: Always use HTTPS for pfSense connections
2. **Limit Access**: Use firewall rules to restrict MCP server access
3. **Secure Credentials**: Never commit credentials to version control
4. **SSH Keys**: Use key-based authentication for SSH method

## Troubleshooting

### Connection Issues
```bash
# Test connection
curl -k https://your-pfsense/api/v1/status/system \
  -H "Authorization: your-key your-secret"

# Check logs
docker logs pfsense-mcp-server
```

### Common Problems

1. **SSL Certificate Error**: Set `VERIFY_SSL=false` for self-signed certs
2. **Authentication Failed**: Verify API keys/credentials are correct
3. **Connection Timeout**: Check firewall rules and network connectivity
4. **Version Mismatch**: Ensure PFSENSE_VERSION matches your installation

## Development

### Local Development
```bash
# Install dependencies
pip install -r requirements-simple.txt

# Run locally
python main_fastmcp.py

# Run tests
python -m pytest tests/
```

### Adding Custom Tools

```python
@mcp.tool()
async def custom_tool(param1: str) -> Dict[str, Any]:
    """Your custom tool description"""
    result = await connection_manager.execute("your.command", {"param": param1})
    return {"status": "success", "data": result}
```

## License

MIT License - See LICENSE file for details