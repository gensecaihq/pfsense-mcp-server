# pfSense REST API v2 Installation & Configuration Guide

This guide covers installing and configuring the pfSense REST API v2 package by jaredhendrickson13 for use with the pfSense MCP Server.

## 🎯 Supported Versions

| pfSense Version | API Package | Status | Notes |
|----------------|-------------|--------|--------|
| **pfSense CE 2.8.0** | ✅ Supported | Production Ready | Recommended for Community Edition |
| **pfSense Plus 24.11** | ✅ Supported | Production Ready | Recommended for Plus Edition |
| **32-bit builds** | ❌ Not Supported | N/A | Only amd64 builds supported |

## 📦 Installation

### Prerequisites
- pfSense CE 2.8.0 or pfSense Plus 24.11
- amd64 architecture (64-bit)
- Internet connectivity for package download
- Administrative access to pfSense

### Step 1: Install the API Package

Connect to your pfSense system via SSH or console and run the appropriate command:

#### For pfSense CE 2.8.0:
```bash
pkg-static add https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-2.8.0-pkg-RESTAPI.pkg
```

#### For pfSense Plus 24.11:
```bash
pkg-static -C /dev/null add https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-24.11-pkg-RESTAPI.pkg
```

### Step 2: Verify Installation

1. Navigate to **System → REST API** in the pfSense webConfigurator
2. You should see the REST API configuration page
3. Check **System → REST API → Documentation** for the interactive Swagger UI

## ⚙️ Configuration

### Step 3: Configure Authentication

Navigate to **System → REST API → Settings** and configure your preferred authentication method:

#### Option A: API Key Authentication (Recommended)
1. Select **API Key** as authentication method
2. Generate an API key:
   - Go to **System → User Manager**
   - Edit your user account
   - Generate an API key in the user settings
3. Note the API key for your MCP server configuration

#### Option B: Basic Authentication
1. Select **Basic Authentication**
2. Use existing pfSense username/password
3. Less secure than API keys but simpler to configure

#### Option C: JWT Authentication
1. Select **JWT Authentication**
2. Configure token expiry (default: 1 hour)
3. Most secure but requires token refresh logic

### Step 4: Configure API Access

1. **Enable the API**: Ensure the REST API is enabled
2. **Set allowed interfaces**: Configure which interfaces can access the API
3. **Configure HTTPS**: Enable HTTPS for secure API access
4. **Set rate limits**: Configure appropriate rate limiting

### Step 5: User Privileges

The API uses granular privileges. Assign appropriate privileges to your API user:

1. Go to **System → User Manager**
2. Edit the user that will access the API
3. Assign necessary privileges based on required functionality:
   - **System: REST API**: Base API access
   - **Firewall: Rules**: For firewall rule management
   - **Interfaces**: For interface management
   - **Services**: For service control
   - **VPN**: For VPN management

## 🔧 MCP Server Configuration

### Step 6: Update Environment Variables

Create or update your `.env` file:

```bash
# pfSense Connection
PFSENSE_URL=https://your-pfsense.local
PFSENSE_VERSION=CE_2_8_0  # or PLUS_24_11

# Authentication (choose one method)
AUTH_METHOD=api_key  # options: api_key, basic, jwt

# API Key Authentication
PFSENSE_API_KEY=your-generated-api-key-here

# Basic Authentication (if using basic auth)
PFSENSE_USERNAME=admin
PFSENSE_PASSWORD=your-password

# SSL Configuration
VERIFY_SSL=true

# MCP Server Settings
MCP_HOST=0.0.0.0
MCP_PORT=8000
DEBUG=false
```

### Step 7: Test Connection

Run the connection test:

```bash
python3 -c "
import asyncio
from pfsense_api_integration import PfSenseAPIv2Client, AuthMethod, PfSenseVersion

async def test():
    client = PfSenseAPIv2Client(
        host='https://your-pfsense.local',
        auth_method=AuthMethod.API_KEY,
        api_key='your-api-key',
        version=PfSenseVersion.CE_2_8_0
    )
    
    connected = await client.test_connection()
    if connected:
        print('✅ Connection successful!')
        status = await client.get_system_status()
        print(f'System status: {status}')
    else:
        print('❌ Connection failed!')
    
    await client.close()

asyncio.run(test())
"
```

## 🚀 Running the MCP Server

### Step 8: Start the Server

```bash
# Install dependencies
pip install -r requirements-fastmcp.txt

# Run the updated MCP server
python main_pfsense_api_v2.py
```

### Step 9: Configure Claude Desktop

Update your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "pfsense-v2": {
      "command": "python",
      "args": ["/path/to/main_pfsense_api_v2.py"],
      "env": {
        "PFSENSE_URL": "https://your-pfsense.local",
        "PFSENSE_VERSION": "CE_2_8_0",
        "AUTH_METHOD": "api_key",
        "PFSENSE_API_KEY": "your-api-key",
        "VERIFY_SSL": "true"
      }
    }
  }
}
```

## 🔍 Available API Endpoints

The pfSense REST API v2 provides 200+ endpoints. Key categories include:

### System & Status
- `/api/v2/status/system` - System status
- `/api/v2/status/interface` - Interface status
- `/api/v2/system/config/backup` - Configuration backups

### Firewall
- `/api/v2/firewall/rule` - Firewall rules
- `/api/v2/firewall/nat/rule` - NAT rules
- `/api/v2/firewall/alias` - Aliases
- `/api/v2/firewall/apply` - Apply changes

### Services
- `/api/v2/services` - Service management
- `/api/v2/services/dhcpd` - DHCP service
- `/api/v2/services/unbound` - DNS resolver

### VPN
- `/api/v2/status/ipsec` - IPsec status
- `/api/v2/status/openvpn` - OpenVPN status

### Diagnostics
- `/api/v2/diagnostics/arp_table` - ARP table
- `/api/v2/diagnostics/log` - System logs

## 🛠️ Troubleshooting

### Common Issues

1. **Package not found**
   - Verify pfSense version matches exactly
   - Check internet connectivity
   - Try manual download and install

2. **Authentication failures**
   - Verify API key is correct
   - Check user privileges
   - Ensure API is enabled

3. **Permission denied**
   - Check user has required privileges
   - Verify API access is enabled for your interface
   - Check firewall rules allow API access

4. **SSL/TLS errors**
   - Set `VERIFY_SSL=false` for testing (not recommended for production)
   - Install proper SSL certificate
   - Check certificate validity

### Debugging

Enable debug logging:

```bash
export DEBUG=true
python main_pfsense_api_v2.py
```

Check API status in pfSense:
- **System → REST API → Documentation** - Access Swagger UI
- **Status → System Logs → System** - Check for API errors

### API Documentation

Access the interactive API documentation:
- Local: `https://your-pfsense.local/api/v2/schema/openapi`
- Online: https://pfrest.org/api-docs/

## 🔄 Maintenance

### Package Updates

The API package must be reinstalled after pfSense system updates:

```bash
# After pfSense update, reinstall the package
pkg-static add https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-[VERSION]-pkg-RESTAPI.pkg
```

### Monitoring

Monitor API usage and performance:
- Check system logs for API errors
- Monitor resource usage during API calls
- Set up alerting for API failures

## 📋 Example MCP Commands

Once configured, you can use these commands in Claude:

```
"Show me the system status"
"List all firewall rules"
"Block IP address 192.168.1.100"
"Create a firewall rule to allow port 80"
"Show DHCP leases"
"Get VPN status"
"Create a configuration backup"
```

## 🔗 Resources

- **Project Repository**: https://github.com/jaredhendrickson13/pfsense-api
- **Documentation**: https://pfrest.org/
- **API Reference**: https://pfrest.org/api-docs/
- **Issues & Support**: https://github.com/jaredhendrickson13/pfsense-api/issues

## ⚠️ Important Notes

1. **Version Compatibility**: Ensure exact version match between pfSense and API package
2. **Security**: Always use HTTPS and strong authentication in production
3. **Backups**: Create configuration backups before making changes via API
4. **Testing**: Test all API operations in a non-production environment first
5. **Updates**: Package must be reinstalled after pfSense system updates

## 🆘 Support

For API package issues:
- Check GitHub issues: https://github.com/jaredhendrickson13/pfsense-api/issues
- Review documentation: https://pfrest.org/

For MCP server issues:
- Check server logs for detailed error messages
- Verify environment configuration
- Test API connectivity independently