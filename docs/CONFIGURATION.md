# Configuration Reference

Complete reference for all configuration options in the pfSense Enhanced MCP Server.

## 📋 Configuration File

The server uses environment variables that can be set in a `.env` file. Use `.env.enhanced` as a template:

```bash
cp .env.enhanced .env
```

## 🔧 Core Connection Settings

### Required Settings

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `PFSENSE_URL` | string | pfSense base URL | `https://pfsense.local` |
| `PFSENSE_VERSION` | enum | pfSense version | `CE_2_8_0`, `PLUS_24_11` |
| `AUTH_METHOD` | enum | Authentication method | `api_key`, `basic`, `jwt` |

### Authentication Options

#### API Key Authentication (Recommended)
```bash
AUTH_METHOD=api_key
PFSENSE_API_KEY=your-api-key-here
```

#### Basic Authentication
```bash
AUTH_METHOD=basic
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password
```

#### JWT Authentication
```bash
AUTH_METHOD=jwt
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password
JWT_EXPIRY_HOURS=1
```

## 🔒 SSL/TLS Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VERIFY_SSL` | boolean | `true` | Verify SSL certificates |
| `SSL_CERT_PATH` | string | - | Path to custom certificate |

**Examples:**
```bash
# Production (verify certificates)
VERIFY_SSL=true

# Development/Testing (skip verification)
VERIFY_SSL=false

# Custom certificate
VERIFY_SSL=true
SSL_CERT_PATH=/path/to/custom/cert.pem
```

## ✨ Enhanced API Features

### HATEOAS Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_HATEOAS` | boolean | `false` | Enable navigation links |

```bash
# Enable HATEOAS for API discovery
ENABLE_HATEOAS=true
```

**Impact:**
- **Enabled**: API responses include `_links` section with navigation
- **Disabled**: Compact responses without navigation links

### Pagination Settings

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEFAULT_PAGE_SIZE` | integer | `20` | Default items per page |
| `MAX_PAGE_SIZE` | integer | `100` | Maximum allowed page size |

```bash
# Configure pagination
DEFAULT_PAGE_SIZE=25
MAX_PAGE_SIZE=200
```

### Caching Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_CACHING` | boolean | `true` | Enable response caching |
| `CACHE_TTL` | integer | `300` | Cache TTL in seconds |

```bash
# Configure caching
ENABLE_CACHING=true
CACHE_TTL=600  # 10 minutes
```

## 🚀 MCP Server Settings

### Basic Server Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MCP_HOST` | string | `0.0.0.0` | Server bind address |
| `MCP_PORT` | integer | `8000` | Server port |
| `MCP_MODE` | enum | `http` | Server mode (`http`, `stdio`) |

```bash
# HTTP server mode
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_MODE=http

# stdio mode for Claude Desktop
MCP_MODE=stdio
```

### Debug Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEBUG` | boolean | `false` | Enable debug mode |
| `LOG_LEVEL` | enum | `INFO` | Logging level |
| `LOG_FORMAT` | enum | `json` | Log format |
| `LOG_FILE` | string | `/var/log/...` | Log file path |

```bash
# Development debugging
DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# Production logging
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/pfsense-mcp/enhanced.log
```

## 🔐 Security Configuration

### Rate Limiting

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_RATE_LIMITING` | boolean | `true` | Enable rate limiting |
| `RATE_LIMIT_REQUESTS` | integer | `100` | Requests per minute |
| `RATE_LIMIT_BURST` | integer | `20` | Burst requests allowed |

```bash
# Conservative rate limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_BURST=10

# Aggressive rate limiting
RATE_LIMIT_REQUESTS=300
RATE_LIMIT_BURST=50
```

### Access Control

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_ACCESS_LOG` | boolean | `true` | Log API access |
| `ENABLE_ERROR_LOG` | boolean | `true` | Log errors |

## ⚡ Performance Settings

### Connection Management

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CONNECTION_TIMEOUT` | integer | `30` | Request timeout (seconds) |
| `MAX_RETRIES` | integer | `3` | Maximum retry attempts |
| `RETRY_DELAY` | integer | `1` | Retry delay (seconds) |
| `CONCURRENT_REQUESTS` | integer | `10` | Max concurrent requests |
| `POOL_CONNECTIONS` | integer | `20` | Connection pool size |

```bash
# High-performance settings
CONNECTION_TIMEOUT=60
MAX_RETRIES=5
CONCURRENT_REQUESTS=20
POOL_CONNECTIONS=50

# Conservative settings
CONNECTION_TIMEOUT=15
MAX_RETRIES=2
CONCURRENT_REQUESTS=5
POOL_CONNECTIONS=10
```

### Query Optimization

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEFAULT_SORT_ORDER` | enum | `asc` | Default sort order |
| `DEFAULT_SORT_FIELD` | string | `id` | Default sort field |
| `ENABLE_REGEX_FILTERS` | boolean | `true` | Allow regex patterns |
| `MAX_FILTER_DEPTH` | integer | `5` | Max nested filters |

```bash
# Query settings
DEFAULT_SORT_ORDER=desc
DEFAULT_SORT_FIELD=timestamp
ENABLE_REGEX_FILTERS=true
MAX_FILTER_DEPTH=10
```

## 🎛️ Control Parameter Defaults

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEFAULT_APPLY_IMMEDIATELY` | boolean | `false` | Auto-apply changes |
| `DEFAULT_ASYNC_MODE` | boolean | `true` | Use async operations |
| `ENABLE_BULK_OPERATIONS` | boolean | `true` | Allow bulk operations |

```bash
# Immediate application mode
DEFAULT_APPLY_IMMEDIATELY=true
DEFAULT_ASYNC_MODE=false

# Batch operation mode  
DEFAULT_APPLY_IMMEDIATELY=false
DEFAULT_ASYNC_MODE=true
ENABLE_BULK_OPERATIONS=true
```

## 🔬 Advanced Features

### Object ID Management

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_OBJECT_ID_TRACKING` | boolean | `true` | Track ID changes |
| `ENABLE_LINK_FOLLOWING` | boolean | `true` | Allow HATEOAS navigation |
| `ENABLE_FIELD_VALIDATION` | boolean | `true` | Validate field values |
| `ENABLE_TYPE_COERCION` | boolean | `true` | Auto-convert types |

### Monitoring & Metrics

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_METRICS` | boolean | `false` | Enable Prometheus metrics |
| `METRICS_PORT` | integer | `9090` | Metrics endpoint port |
| `ENABLE_HEALTH_CHECKS` | boolean | `true` | Enable health endpoints |
| `HEALTH_CHECK_INTERVAL` | integer | `30` | Health check interval |

```bash
# Enable monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
ENABLE_HEALTH_CHECKS=true
HEALTH_CHECK_INTERVAL=15
```

## 🌐 Integration Settings

### Claude Desktop Optimization

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CLAUDE_DESKTOP_CONFIG` | boolean | `true` | Optimize for Claude |
| `ENABLE_NATURAL_LANGUAGE` | boolean | `true` | Enable NLP processing |
| `NLP_CONFIDENCE_THRESHOLD` | float | `0.7` | Min confidence for NLP |

### CORS Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_CORS` | boolean | `false` | Enable CORS |
| `ALLOWED_ORIGINS` | string | `*` | CORS allowed origins |

```bash
# Web interface support
ENABLE_CORS=true
ALLOWED_ORIGINS=https://admin.example.com,https://dashboard.local
```

## 💾 Backup & Recovery

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AUTO_BACKUP_BEFORE_CHANGES` | boolean | `true` | Auto backup configs |
| `BACKUP_RETENTION_DAYS` | integer | `30` | Backup retention period |
| `ENABLE_CHANGE_TRACKING` | boolean | `true` | Track all changes |

```bash
# Backup configuration
AUTO_BACKUP_BEFORE_CHANGES=true
BACKUP_RETENTION_DAYS=90
ENABLE_CHANGE_TRACKING=true
```

## 📡 Notifications (Optional)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_NOTIFICATIONS` | boolean | `false` | Enable notifications |
| `NOTIFICATION_WEBHOOK_URL` | string | - | Webhook URL |
| `NOTIFICATION_EVENTS` | string | `critical,error` | Events to notify |

```bash
# Webhook notifications
ENABLE_NOTIFICATIONS=true
NOTIFICATION_WEBHOOK_URL=https://hooks.slack.com/services/...
NOTIFICATION_EVENTS=critical,error,security
```

## 📊 API Quotas & Limits

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_RESULTS_PER_REQUEST` | integer | `1000` | Max results per request |
| `MAX_CONCURRENT_USERS` | integer | `50` | Max concurrent users |
| `API_QUOTA_PER_HOUR` | integer | `10000` | API calls per hour |

## 🎨 Customization

### Custom Headers

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CUSTOM_USER_AGENT` | string | `pfSense-Enhanced-MCP/4.0.0` | Custom User-Agent |
| `CUSTOM_HEADERS` | json | `{}` | Additional headers |

```bash
# Custom headers
CUSTOM_USER_AGENT=MyCompany-pfSense-Bot/1.0
CUSTOM_HEADERS={"X-Company": "MyCompany", "X-Environment": "production"}
```

### Environment Identification

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENVIRONMENT` | enum | `production` | Environment type |
| `DEPLOYMENT_ID` | string | `pfsense-mcp-01` | Deployment identifier |
| `INSTANCE_NAME` | string | `main` | Instance name |

```bash
# Environment settings
ENVIRONMENT=staging
DEPLOYMENT_ID=pfsense-test-01
INSTANCE_NAME=test-instance
```

## 📝 Configuration Templates

### Minimal Production Configuration

```bash
# Required settings
PFSENSE_URL=https://pfsense.local
PFSENSE_API_KEY=your-api-key
PFSENSE_VERSION=CE_2_8_0
AUTH_METHOD=api_key
VERIFY_SSL=true

# Basic server
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_MODE=http

# Security
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=100
```

### Development Configuration

```bash
# Required settings  
PFSENSE_URL=https://pfsense-dev.local
PFSENSE_API_KEY=dev-api-key
PFSENSE_VERSION=CE_2_8_0
AUTH_METHOD=api_key
VERIFY_SSL=false

# Development features
DEBUG=true
LOG_LEVEL=DEBUG
ENABLE_HATEOAS=true
DEFAULT_PAGE_SIZE=10

# Relaxed limits
RATE_LIMIT_REQUESTS=1000
CONNECTION_TIMEOUT=60
```

### High-Performance Configuration

```bash
# Performance optimizations
ENABLE_CACHING=true
CACHE_TTL=600
CONCURRENT_REQUESTS=20
POOL_CONNECTIONS=50
CONNECTION_TIMEOUT=30

# Bulk operations
ENABLE_BULK_OPERATIONS=true
DEFAULT_ASYNC_MODE=true
MAX_RESULTS_PER_REQUEST=2000

# Monitoring
ENABLE_METRICS=true
ENABLE_HEALTH_CHECKS=true
```

### Enterprise Configuration

```bash
# Security hardening
VERIFY_SSL=true
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=200
ENABLE_ACCESS_LOG=true
ENABLE_ERROR_LOG=true

# Backup & compliance
AUTO_BACKUP_BEFORE_CHANGES=true
BACKUP_RETENTION_DAYS=90
ENABLE_CHANGE_TRACKING=true

# Monitoring & alerting
ENABLE_METRICS=true
ENABLE_NOTIFICATIONS=true
NOTIFICATION_WEBHOOK_URL=https://alerts.company.com/webhook
NOTIFICATION_EVENTS=critical,error,security,compliance

# Resource limits
MAX_CONCURRENT_USERS=100
API_QUOTA_PER_HOUR=50000
```

## 🔍 Configuration Validation

### Required Variables Check

The server validates required configuration on startup:

1. **Connection Settings**: `PFSENSE_URL`, `PFSENSE_VERSION`
2. **Authentication**: At least one auth method configured
3. **Basic Server**: `MCP_HOST`, `MCP_PORT`

### Configuration Testing

```bash
# Test configuration
python -c "
import os
from main_enhanced_mcp import get_api_client
client = get_api_client()
print('✅ Configuration valid')
"

# Test enhanced features
python test_enhanced_features.py
```

### Common Configuration Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Missing API key | Authentication failed | Set `PFSENSE_API_KEY` |
| Invalid URL | Connection timeout | Check `PFSENSE_URL` format |
| SSL errors | Certificate verification failed | Set `VERIFY_SSL=false` or add certificate |
| Permission denied | API calls rejected | Check pfSense user privileges |
| Poor performance | Slow responses | Tune performance settings |

## 🔄 Configuration Updates

### Runtime Configuration

Some settings can be changed at runtime:

```python
# Enable HATEOAS dynamically
await enable_hateoas()

# Disable HATEOAS for performance
await disable_hateoas()
```

### Configuration Reload

For most settings, restart the server after changes:

```bash
# Restart HTTP server
python main_enhanced_mcp.py

# Or with systemd
systemctl restart pfsense-mcp
```

---

For more information, see:
- [Enhanced Features Guide](ENHANCED_FEATURES.md)
- [MCP Tools Reference](MCP_TOOLS.md)
- [pfSense API Installation Guide](../PFSENSE_API_INSTALLATION.md)