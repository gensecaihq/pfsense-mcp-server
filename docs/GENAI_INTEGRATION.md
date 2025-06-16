# GenAI Integration Guide

This guide explains how to integrate the pfSense MCP Server with various GenAI applications that support the Model Context Protocol.

## Supported GenAI Applications

### 1. Claude Desktop (Anthropic)

See [CLAUDE_DESKTOP_SETUP.md](CLAUDE_DESKTOP_SETUP.md) for detailed setup.

### 2. Continue (VS Code Extension)

Add to your Continue config (`~/.continue/config.json`):

```json
{
  "models": [...],
  "mcpServers": {
    "pfsense": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--env-file", "/path/to/.env",
        "pfsense-mcp:latest"
      ]
    }
  }
}
```

### 3. Cody (Sourcegraph)

Configure in Cody settings:

```json
{
  "cody.mcp.servers": {
    "pfsense": {
      "command": "python",
      "args": ["/path/to/main.py"],
      "env": {
        "MCP_MODE": "stdio",
        "PFSENSE_URL": "https://your-pfsense.local"
      }
    }
  }
}
```

### 4. Custom MCP Client

For custom integrations, connect via stdio:

```python
import subprocess
import json

# Start MCP server
proc = subprocess.Popen(
    ["python", "main.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env={
        "MCP_MODE": "stdio",
        "PFSENSE_URL": "https://pfsense.local",
        # ... other env vars
    }
)

# Send request
request = {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
}
proc.stdin.write(json.dumps(request) + "\n")
proc.stdin.flush()

# Read response
response = json.loads(proc.stdout.readline())
```

### 5. HTTP API Mode

For web-based GenAI apps, run in HTTP mode:

```bash
docker run -p 8000:8000 \
  -e MCP_MODE=http \
  --env-file .env \
  pfsense-mcp:latest
```

Then connect to `http://localhost:8000/mcp`:

```javascript
// Example JavaScript client
const response = await fetch('http://localhost:8000/mcp', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    jsonrpc: '2.0',
    method: 'prompts/process',
    params: {
      prompt: 'Show me blocked IPs'
    },
    id: 1
  })
});

const result = await response.json();
```

## MCP Protocol Overview

The Model Context Protocol (MCP) enables:
- **Tools**: Functions the AI can call
- **Resources**: Data the AI can access
- **Prompts**: Natural language processing
- **Logging**: Audit trail

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": {
    // method-specific parameters
  },
  "id": "unique_id"
}
```

### Response Format

```json
{
  "jsonrpc": "2.0",
  "result": {
    // method result
  },
  "id": "unique_id"
}
```

## Integration Examples

### Example 1: Monitoring Dashboard

```python
# Connect to MCP server
mcp = MCPClient("http://localhost:8000/mcp")

# Get system status
status = await mcp.call("tools/call", {
  "name": "system_status",
  "arguments": {}
})

# Get blocked IPs
blocked = await mcp.call("tools/call", {
  "name": "show_blocked_ips",
  "arguments": {}
})

# Display in dashboard
dashboard.update(status, blocked)
```

### Example 2: Slack Bot Integration

```python
@slack_command("/pfsense")
async def handle_pfsense_command(command: str):
    # Send to MCP server
    result = await mcp.call("prompts/process", {
        "prompt": command
    })
    
    # Format for Slack
    return format_slack_message(result)
```

### Example 3: Automated Compliance

```python
# Schedule daily compliance checks
@schedule.daily
async def compliance_check():
    frameworks = ["PCI-DSS", "HIPAA", "SOC2"]
    
    for framework in frameworks:
        result = await mcp.call("tools/call", {
            "name": "run_compliance_check",
            "arguments": {"framework": framework}
        })
        
        if result["status"] == "FAIL":
            send_alert(f"{framework} compliance failed")
```

## Security Considerations

1. **Authentication**: Always use secure tokens
2. **Network**: Use HTTPS/TLS for remote connections
3. **Access Control**: Implement proper RBAC
4. **Audit**: Enable logging for all operations
5. **Rate Limiting**: Prevent abuse

## Performance Tips

1. **Caching**: Enable Redis for better performance
2. **Connection Pooling**: Reuse connections
3. **Batch Operations**: Group related calls
4. **Async Operations**: Use async/await patterns

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check if MCP server is running
   - Verify port is not blocked
   - Check firewall rules

2. **Permission Denied**
   - Verify access level
   - Check token validity
   - Review audit logs

3. **Slow Response**
   - Check pfSense load
   - Enable caching
   - Optimize queries

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python main.py
```

## Support

- GitHub Issues: [Report bugs](https://github.com/yourusername/pfsense-mcp-server)
- Documentation: [Full docs](https://docs.example.com)
- Community: [Discord/Slack]
