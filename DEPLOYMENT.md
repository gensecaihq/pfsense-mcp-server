# pfSense MCP Server - Deployment Guide

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Methods](#deployment-methods)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## Overview

The pfSense MCP Server is built on the FastMCP framework, fully containerized with Docker. It connects to pfSense via the [REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) and supports both pfSense CE and Plus versions.

### Key Features
- **FastMCP Framework**: High-performance MCP implementation
- **Multi-version Support**: Compatible with pfSense CE 2.8.0+ and Plus 24.11+
- **REST API v2**: Connects via the pfSense REST API v2 package (by jaredhendrickson13)
- **Three Auth Methods**: Basic Auth, API Key, and JWT
- **Dual Transport**: stdio mode (Claude Desktop/Code) and streamable-http mode (remote access)
- **Fully Dockerized**: Multi-stage build with non-root user

## Prerequisites

### System Requirements
- Docker Engine 20.10+ and Docker Compose 2.0+ (for Docker deployment)
- Python 3.11+ (for local deployment)
- Network connectivity to pfSense instance

### pfSense Requirements
- pfSense CE 2.8.0+ or Plus 24.11+
- [pfSense REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) installed and enabled
- API access configured at **System > REST API** in pfSense web UI
- Valid credentials (local database user) or API key

See [PFSENSE_API_INSTALLATION.md](PFSENSE_API_INSTALLATION.md) for detailed REST API package setup.

## Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your pfSense URL and credentials
```

3. **Run locally (stdio mode)**
```bash
pip install -r requirements.txt
python -m src.main
```

4. **Or run with Docker (HTTP mode)**
```bash
docker compose up
```

## Configuration

### Environment Variables

#### Required Variables
```bash
# pfSense Connection
PFSENSE_URL=https://your-pfsense.local
PFSENSE_VERSION=PLUS_24_11    # CE_2_8_0, CE_2_8_1, PLUS_24_11, PLUS_25_11

# Authentication — choose one method:
AUTH_METHOD=basic              # basic, api_key, or jwt

# For basic or jwt auth:
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password

# For api_key auth:
# PFSENSE_API_KEY=your-key    # Generate at System > REST API > Keys
```

#### Optional Variables
```bash
VERIFY_SSL=false               # Set true if using a trusted SSL certificate
ENABLE_HATEOAS=false           # Include HATEOAS links in API responses
LOG_LEVEL=INFO                 # DEBUG, INFO, WARNING, ERROR

# HTTP transport mode
MCP_TRANSPORT=stdio            # stdio or streamable-http
MCP_HOST=0.0.0.0               # Bind address for HTTP mode
MCP_PORT=3000                  # Port for HTTP mode
MCP_API_KEY=your-bearer-token  # Required for HTTP mode (bearer auth)
```

### Authentication Methods

The pfSense REST API v2 supports three methods (multiple can be enabled simultaneously in pfSense at **System > REST API**):

**Basic Auth** — simplest, uses existing pfSense credentials:
```bash
AUTH_METHOD=basic
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password
```

**API Key** — generate at System > REST API > Keys:
```bash
AUTH_METHOD=api_key
PFSENSE_API_KEY=your-key
```

**JWT** — auto-obtains short-lived tokens (default 1 hour):
```bash
AUTH_METHOD=jwt
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password
```

> **Note:** Only local database users are supported for all auth methods (not LDAP/RADIUS).

## Deployment Methods

### 1. Local (stdio mode — for Claude Desktop / Claude Code)

```bash
pip install -r requirements.txt
python -m src.main
```

### 2. Docker Compose (HTTP mode — recommended for remote access)

```bash
# Configure .env then:
docker compose up -d
```

The `docker-compose.yml` runs in `streamable-http` mode on port 3000 with bearer auth (`MCP_API_KEY` required).

### 3. Docker Run

```bash
# Build
docker build -t pfsense-mcp .

# Run in stdio mode
docker run --rm \
  -e PFSENSE_URL=https://your-pfsense.local \
  -e AUTH_METHOD=basic \
  -e PFSENSE_USERNAME=admin \
  -e PFSENSE_PASSWORD=your-password \
  -e VERIFY_SSL=false \
  pfsense-mcp

# Run in HTTP mode
docker run -d \
  --name pfsense-mcp \
  -p 3000:3000 \
  -e PFSENSE_URL=https://your-pfsense.local \
  -e AUTH_METHOD=api_key \
  -e PFSENSE_API_KEY=your-key \
  -e MCP_API_KEY=your-bearer-token \
  -e VERIFY_SSL=false \
  pfsense-mcp -t streamable-http
```

### 4. Claude Desktop Integration

Add to Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "pfsense": {
      "command": "python",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/pfsense-mcp-server",
      "env": {
        "PFSENSE_URL": "https://your-pfsense.local",
        "PFSENSE_USERNAME": "admin",
        "PFSENSE_PASSWORD": "your-password",
        "AUTH_METHOD": "basic",
        "PFSENSE_VERSION": "PLUS_24_11",
        "VERIFY_SSL": "false"
      }
    }
  }
}
```

## Security

### Bearer Auth for HTTP Transport

HTTP transport mode requires `MCP_API_KEY` for bearer token authentication. The server will refuse to start in HTTP mode without it (fail-closed).

### SSL/TLS

pfSense typically uses a self-signed certificate. Set `VERIFY_SSL=false` for testing, or install a trusted certificate on your pfSense instance for production.

### Access Controls

The pfSense REST API v2 provides built-in access controls at **System > REST API > Access Lists**:
- Source IP/network restrictions
- User-based restrictions
- Time-based schedules

### Logging

```bash
# View logs
docker compose logs -f pfsense-mcp

# Enable debug logging
LOG_LEVEL=DEBUG python -m src.main
```

## Troubleshooting

### Common Issues

1. **Connection refused**
   - Verify `PFSENSE_URL` is correct and reachable
   - Check that the REST API package is installed at **System > REST API**
   - Ensure the API is listening on the correct interface

2. **401 Unauthorized**
   - For `api_key` auth: verify key is valid (System > REST API > Keys)
   - For `basic`/`jwt` auth: verify username/password for a local database user
   - Check that your auth method is enabled at System > REST API settings

3. **SSL errors**
   - Set `VERIFY_SSL=false` if pfSense uses a self-signed certificate

4. **HTTP mode won't start**
   - `MCP_API_KEY` must be set for streamable-http transport

### Debug Mode

```bash
LOG_LEVEL=DEBUG python -m src.main
```

## License

MIT License — see [LICENSE](LICENSE) for details.
