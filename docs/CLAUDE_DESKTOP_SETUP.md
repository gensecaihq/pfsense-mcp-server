# Claude Desktop Setup Guide for pfSense MCP Server

This guide explains how to configure Claude Desktop to use the pfSense MCP Server.

## Prerequisites

1. Claude Desktop app installed
2. pfSense MCP Server installed and configured
3. pfSense API access configured

## Setup Methods

### Method 1: Docker Container (Recommended)

1. Build the Docker image:
```bash
docker build -t pfsense-mcp:latest .
```

2. Find your Claude Desktop config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

3. Add the MCP server configuration:
```json
{
  "mcpServers": {
    "pfsense": {
      "command": "docker",
      "args": [
        "run", 
        "-i", 
        "--rm",
        "--env-file", "/path/to/your/.env",
        "pfsense-mcp:latest"
      ],
      "env": {
        "MCP_MODE": "stdio"
      }
    }
  }
}
```

### Method 2: Local Python

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure Claude Desktop:
```json
{
  "mcpServers": {
    "pfsense": {
      "command": "python",
      "args": ["/full/path/to/pfsense-mcp-server/main.py"],
      "env": {
        "MCP_MODE": "stdio",
        "PFSENSE_URL": "https://192.168.1.1",
        "PFSENSE_CONNECTION_METHOD": "rest",
        "PFSENSE_API_KEY": "your-api-key",
        "PFSENSE_API_SECRET": "your-api-secret",
        "DEFAULT_ACCESS_LEVEL": "READ_ONLY"
      }
    }
  }
}
```

### Method 3: Virtual Environment

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure Claude Desktop:
```json
{
  "mcpServers": {
    "pfsense": {
      "command": "/path/to/venv/bin/python",
      "args": ["/path/to/pfsense-mcp-server/main.py"],
      "env": {
        "MCP_MODE": "stdio",
        "PFSENSE_URL": "https://192.168.1.1",
        "PFSENSE_CONNECTION_METHOD": "rest",
        "PFSENSE_API_KEY": "your-api-key",
        "PFSENSE_API_SECRET": "your-api-secret"
      }
    }
  }
}
```

## Configuration Options

### Connection Methods

1. **REST API** (Recommended for pfSense 2.5+):
```json
{
  "PFSENSE_CONNECTION_METHOD": "rest",
  "PFSENSE_API_KEY": "your-api-key",
  "PFSENSE_API_SECRET": "your-api-secret"
}
```

2. **XML-RPC** (Legacy):
```json
{
  "PFSENSE_CONNECTION_METHOD": "xmlrpc",
  "PFSENSE_USERNAME": "admin",
  "PFSENSE_PASSWORD": "password"
}
```

3. **SSH** (Advanced):
```json
{
  "PFSENSE_CONNECTION_METHOD": "ssh",
  "PFSENSE_SSH_HOST": "192.168.1.1",
  "PFSENSE_SSH_USERNAME": "admin",
  "PFSENSE_SSH_KEY_PATH": "/path/to/id_rsa"
}
```

### Access Levels

Configure default access level:
```json
{
  "DEFAULT_ACCESS_LEVEL": "READ_ONLY"  // or SECURITY_WRITE, ADMIN_WRITE, etc.
}
```

## Testing the Connection

1. Restart Claude Desktop after configuration

2. In Claude, you should see "pfsense" in the MCP tools list

3. Test with simple commands:
   - "Show me the pfSense system status"
   - "List network interfaces"
   - "What IPs are currently blocked?"

## Troubleshooting

### MCP Server Not Appearing

1. Check config file syntax (valid JSON)
2. Verify file paths are absolute
3. Check Claude Desktop logs:
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%LOCALAPPDATA%\Claude\Logs\`

### Connection Errors

1. Test connection manually:
```bash
python scripts/test_connection.py
```

2. Check environment variables:
```bash
export PFSENSE_URL=https://192.168.1.1
export PFSENSE_API_KEY=your-key
python main.py
```

3. Verify pfSense API is enabled and accessible

### Permission Errors

Ensure your API key has appropriate permissions in pfSense:
- For READ_ONLY: View permissions
- For SECURITY_WRITE: Firewall rule permissions
- For ADMIN_WRITE: Full admin permissions

## Example Conversations

Once configured, you can have conversations like:

**You**: "Show me the current firewall status"
**Claude**: "I'll check the pfSense firewall status for you..."

**You**: "Are there any suspicious IPs trying to connect?"
**Claude**: "Let me analyze the recent threats..."

**You**: "Block IP 192.168.1.100"
**Claude**: "I'll block that IP address for you..." (requires SECURITY_WRITE)

**You**: "Run a PCI compliance check"
**Claude**: "I'll run a PCI-DSS compliance scan..." (requires COMPLIANCE_READ)

## Security Notes

1. Store API credentials securely
2. Use read-only access by default
3. Enable audit logging
4. Regularly review access logs
5. Use SSL/TLS for connections
