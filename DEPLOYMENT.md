# pfSense MCP Server - Deployment Guide

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Methods](#deployment-methods)
- [Security](#security)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Production Checklist](#production-checklist)

## Overview

The pfSense MCP Server is a production-grade implementation using FastMCP framework, fully containerized with Docker for OS-agnostic deployment. It supports both pfSense CE and Plus versions with multiple connection methods.

### Key Features
- **FastMCP Framework**: High-performance, pythonic MCP implementation
- **Multi-version Support**: Compatible with pfSense CE 2.8.0+ and Plus 24.11+
- **Multiple Connection Methods**: REST API, XML-RPC, and SSH
- **Production-Ready**: Circuit breakers, health checks, monitoring, and logging
- **Fully Dockerized**: Complete containerization with all dependencies
- **Security-First**: Role-based access control, audit logging, and encryption

## Prerequisites

### System Requirements
- Docker Engine 20.10+ and Docker Compose 2.0+
- 2 CPU cores minimum (4 recommended)
- 2GB RAM minimum (4GB recommended)
- 10GB disk space
- Network connectivity to pfSense instance

### pfSense Requirements
- pfSense CE 2.8.0+ or Plus 24.11+
- API access enabled (for REST/XML-RPC)
- SSH access enabled (for SSH method)
- Valid credentials or API keys

## Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/pfsense-mcp-server.git
cd pfsense-mcp-server
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your pfSense credentials and settings
```

3. **Build and run**
```bash
make build
make run
```

4. **Verify deployment**
```bash
make health-check
```

## Configuration

### Environment Variables

#### Required Variables
```bash
# pfSense Connection
PFSENSE_URL=https://your-pfsense.example.com
PFSENSE_VERSION=ce                    # or "plus"
PFSENSE_CONNECTION_METHOD=rest        # rest, xmlrpc, or ssh

# Authentication (choose based on connection method)
# For REST API:
PFSENSE_API_KEY=your-api-key
PFSENSE_API_SECRET=your-api-secret

# For XML-RPC:
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password

# For SSH:
PFSENSE_SSH_HOST=your-pfsense.example.com
PFSENSE_SSH_USERNAME=admin
```

#### Optional Variables
```bash
# Security
MCP_ACCESS_LEVEL=READ_ONLY           # Access control level
IP_WHITELIST=192.168.1.0/24,10.0.0.0/8

# Performance
CACHE_TTL=300                        # Cache TTL in seconds
MCP_WORKERS=4                        # Number of worker processes

# Monitoring
OTEL_ENABLED=true                    # Enable OpenTelemetry
PROMETHEUS_PORT=9091                 # Prometheus metrics port
```

### Access Levels

The server supports hierarchical access levels:

1. **READ_ONLY**: View system status, interfaces, rules
2. **COMPLIANCE_READ**: Run compliance checks, generate reports
3. **SECURITY_WRITE**: Modify firewall rules, block IPs
4. **ADMIN_WRITE**: Full configuration access
5. **EMERGENCY_WRITE**: Emergency lockdown capabilities

## Deployment Methods

### 1. Docker Compose (Recommended)

```bash
# Production deployment with all services
docker-compose up -d

# Minimal deployment (MCP server only)
docker-compose up -d pfsense-mcp redis
```

### 2. Docker Run

```bash
# Build image
docker build -t pfsense-mcp:latest .

# Run container
docker run -d \
  --name pfsense-mcp \
  --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/config:/config:ro \
  -v $(pwd)/logs:/logs \
  -v $(pwd)/data:/data \
  pfsense-mcp:latest
```

### 3. Kubernetes

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pfsense-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pfsense-mcp
  template:
    metadata:
      labels:
        app: pfsense-mcp
    spec:
      containers:
      - name: pfsense-mcp
        image: pfsense-mcp:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: pfsense-mcp-secrets
        - configMapRef:
            name: pfsense-mcp-config
```

### 4. Claude Desktop Integration

For Claude Desktop stdio mode:

```bash
# Run in stdio mode
docker run -it --rm \
  --env-file .env \
  -e MCP_MODE=stdio \
  pfsense-mcp:latest
```

Or use the helper command:
```bash
make cli-mode
```

## Security

### SSL/TLS Configuration

1. **Generate certificates** (for development):
```bash
make generate-certs
```

2. **Use production certificates**:
```bash
# Place certificates in config/ssl/
cp /path/to/cert.pem config/ssl/
cp /path/to/key.pem config/ssl/
```

3. **Enable TLS in Nginx**:
```bash
ENABLE_TLS=true docker-compose up -d nginx
```

### Network Security

1. **Firewall rules**:
```bash
# Allow only specific IPs
IP_WHITELIST=192.168.1.100,10.0.0.0/24
```

2. **Rate limiting** (configured in Nginx):
- API endpoints: 10 requests/second
- Health checks: 1 request/second

3. **Network isolation**:
```yaml
# Docker network configuration
networks:
  mcp-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.25.0.0/16
```

## Monitoring

### Metrics Collection

1. **Prometheus metrics**:
```bash
# View metrics
curl http://localhost:9090/metrics

# Or use the web UI
make metrics
```

2. **Grafana dashboards**:
```bash
# Access Grafana
make grafana
# Default credentials: admin/changeme
```

### Health Checks

```bash
# Check all services
make health-check

# Check specific service
curl http://localhost:8000/health
```

### Logging

Logs are structured JSON and stored in multiple locations:

```bash
# Application logs
docker-compose logs -f pfsense-mcp

# All logs
tail -f logs/*.log

# Audit logs (if database enabled)
docker-compose exec postgres psql -U mcp -d mcp_audit \
  -c "SELECT * FROM audit.logs ORDER BY timestamp DESC LIMIT 10;"
```

## Troubleshooting

### Common Issues

1. **Connection refused**:
```bash
# Check pfSense URL and credentials
curl -k https://your-pfsense.example.com

# Verify network connectivity
docker-compose exec pfsense-mcp ping your-pfsense.example.com
```

2. **Authentication failed**:
```bash
# Test credentials
docker-compose exec pfsense-mcp python -c "
from main_fastmcp import connection_manager
import asyncio
asyncio.run(connection_manager.test_connection())
"
```

3. **Circuit breaker open**:
```bash
# Check circuit breaker status
curl http://localhost:8000/health | jq .circuit_breaker

# Reset by restarting
docker-compose restart pfsense-mcp
```

### Debug Mode

Enable debug logging:
```bash
LOG_LEVEL=DEBUG docker-compose up pfsense-mcp
```

## Production Checklist

### Before Deployment

- [ ] Configure production credentials in `.env`
- [ ] Set appropriate access levels
- [ ] Configure IP whitelist if needed
- [ ] Generate or obtain SSL certificates
- [ ] Set up backup strategy
- [ ] Configure monitoring alerts
- [ ] Review security settings
- [ ] Test failover scenarios

### Deployment Steps

1. **Prepare environment**:
```bash
# Set production mode
export PRODUCTION=true

# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

2. **Verify services**:
```bash
# Check all services are healthy
make health-check

# Run security scan
make security-scan
```

3. **Configure monitoring**:
```bash
# Set up Prometheus alerts
cp config/prometheus/alerts.yml.example config/prometheus/alerts.yml

# Configure Grafana notifications
# Access Grafana and set up notification channels
```

4. **Set up backups**:
```bash
# Manual backup
make backup

# Automated backups (add to crontab)
0 2 * * * cd /path/to/pfsense-mcp-server && make backup
```

### Post-Deployment

1. **Monitor logs**:
```bash
# Watch for errors
docker-compose logs -f pfsense-mcp | grep ERROR
```

2. **Check metrics**:
- CPU usage < 80%
- Memory usage < 80%
- Response time < 1s
- Error rate < 1%

3. **Regular maintenance**:
```bash
# Weekly health check
make health-check

# Monthly security updates
docker-compose pull
make build
make deploy
```

## Advanced Configuration

### High Availability

For HA deployment, use multiple instances behind a load balancer:

```nginx
upstream mcp_backends {
    least_conn;
    server mcp1.internal:8000 max_fails=3 fail_timeout=30s;
    server mcp2.internal:8000 max_fails=3 fail_timeout=30s;
    server mcp3.internal:8000 max_fails=3 fail_timeout=30s;
}
```

### Custom Tools

Add custom tools in `main_fastmcp.py`:

```python
@mcp.tool()
async def custom_tool(param1: str, param2: int = 10) -> Dict[str, Any]:
    """Your custom tool description"""
    # Implementation
    return {"result": "success"}
```

### Integration with CI/CD

GitHub Actions example:

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build and push
        run: |
          docker build -t ${{ secrets.REGISTRY }}/pfsense-mcp:${{ github.sha }} .
          docker push ${{ secrets.REGISTRY }}/pfsense-mcp:${{ github.sha }}
      - name: Deploy
        run: |
          ssh deploy@server "cd /app && docker-compose pull && docker-compose up -d"
```

## Support

For issues and questions:
1. Check the [troubleshooting](#troubleshooting) section
2. Review logs for error messages
3. Open an issue on GitHub with:
   - Environment details
   - Error messages
   - Steps to reproduce

## License

This project is licensed under the MIT License. See LICENSE file for details.