# pfSense MCP Server

A production-grade Model Context Protocol (MCP) server that enables natural language interaction with pfSense firewalls through Claude Desktop and other GenAI applications.

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/yourusername/pfsense-mcp-server)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)

## 🚀 Features

- **Natural Language Interface**: Control pfSense using plain English
- **5 Access Levels**: From read-only monitoring to emergency response
- **Multiple Connection Methods**: REST API, XML-RPC, and SSH
- **6 Functional Categories**: Complete security operations coverage
- **GenAI Integration**: Works with Claude Desktop, Continue, and other MCP clients
- **Production Ready**: Audit logging, rate limiting, caching

## 📋 Quick Start

### 1. Install and Configure

```bash
# Clone the repository
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env  # Add your pfSense details
```

### 2. Run with Docker

```bash
# Build and start
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

### 3. Configure Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "pfsense": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--env-file", "/path/to/.env", "pfsense-mcp:latest"],
      "env": {
        "MCP_MODE": "stdio"
      }
    }
  }
}
```

Or run locally:

```json
{
  "mcpServers": {
    "pfsense": {
      "command": "python",
      "args": ["/path/to/pfsense-mcp-server/main.py"],
      "env": {
        "PFSENSE_URL": "https://your-pfsense.local",
        "PFSENSE_API_KEY": "your-api-key"
      }
    }
  }
}
```

## 🔐 Access Levels

| Level | Description | Example Users |
|-------|-------------|---------------|
| `READ_ONLY` | Monitor and view | Security Analysts |
| `SECURITY_WRITE` | Modify security rules | Security Engineers |
| `ADMIN_WRITE` | Full system access | Administrators |
| `COMPLIANCE_READ` | Audit and compliance | Compliance Officers |
| `EMERGENCY_WRITE` | Emergency response | Incident Responders |

## 💬 Example Prompts

```
"Show me the system status"
"What IPs are currently blocked?"
"Block IP 192.168.1.100"
"Run a PCI compliance check"
"Analyze threats from the last hour"
"EMERGENCY: Block all traffic from Russia"
```

## 📚 Documentation

- [Claude Desktop Setup](docs/CLAUDE_DESKTOP_SETUP.md)
- [GenAI Integration Guide](docs/GENAI_INTEGRATION.md)
- [API Documentation](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Permissions Guide](docs/PERMISSIONS.md)

## 🧪 Testing

```bash
# Test connection
python scripts/test_connection.py

# Run tests
pytest tests/

# Generate token
python scripts/generate_token.py alice READ_ONLY
```

## 📝 License

MIT License - see [LICENSE](LICENSE)
