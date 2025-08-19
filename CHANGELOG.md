# Changelog

All notable changes to the pfSense Enhanced MCP Server project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.0] - 2025-01-19

### 🚀 Major Release - Enhanced API Integration

This is a **major breaking release** that completely transforms the pfSense MCP Server with advanced API features and enterprise-grade capabilities.

#### ✨ Added

**Enhanced API Integration:**
- Full support for [jaredhendrickson13/pfsense-api](https://github.com/jaredhendrickson13/pfsense-api) v2
- Support for pfSense CE 2.8.0 and pfSense Plus 24.11
- Complete REST API v2 client implementation (`pfsense_api_enhanced.py`)

**Advanced Filtering System:**
- 8 filter operators: exact, contains, startswith, endswith, lt, lte, gt, gte, regex
- Multi-field filtering with complex query combinations
- Intelligent search across all pfSense objects
- Performance-optimized filter processing

**Smart Pagination & Sorting:**
- Page-based navigation with configurable page sizes
- Multi-field sorting with ascending/descending options
- Efficient handling of large datasets
- Progressive data loading

**HATEOAS Navigation:**
- Dynamic API discovery through embedded links
- Hypermedia controls for API exploration
- Runtime enable/disable of navigation features
- Self-documenting API relationships

**Control Parameters:**
- Fine-grained operation control (apply, async, placement)
- Bulk operation support with transaction-like behavior
- Position-based object management
- Array manipulation (append, remove operations)

**Object ID Management:**
- Dynamic ID tracking and refresh capabilities
- Field-based object lookup (safer than ID-based)
- Handling of non-persistent pfSense object IDs
- Automatic ID resolution after changes

**25+ Enhanced MCP Tools:**
- `search_interfaces()` - Advanced interface discovery
- `search_firewall_rules()` - Comprehensive rule search
- `search_aliases()` - Intelligent alias management
- `search_dhcp_leases()` - DHCP lease analysis
- `create_firewall_rule_advanced()` - Precise rule creation
- `move_firewall_rule()` - Rule prioritization
- `bulk_block_ips()` - Efficient threat response
- `analyze_blocked_traffic()` - Traffic pattern analysis
- `manage_alias_addresses()` - Dynamic list management
- `follow_api_link()` - HATEOAS navigation
- `refresh_object_ids()` - ID management
- `find_object_by_field()` - Reliable object lookup
- And many more...

**Enterprise Features:**
- Multi-authentication support (API Key, Basic, JWT)
- Advanced caching with TTL management
- Connection pooling and async operations
- Comprehensive audit logging
- Rate limiting and security controls
- Health checks and monitoring endpoints
- Production-ready Docker deployment

**Comprehensive Documentation:**
- Complete setup and installation guides
- Enhanced features documentation
- MCP tools reference
- Configuration reference
- API integration details
- Troubleshooting guides

#### 🔧 Changed

**Breaking Changes:**
- Migrated from XML-RPC to REST API v2 as primary interface
- Updated all MCP tools with enhanced parameters
- New authentication methods (API Key recommended)
- Updated environment configuration format
- Changed response formats to include enhanced metadata

**Configuration Updates:**
- New `.env.enhanced` template with advanced options
- Updated authentication configuration
- Enhanced performance and caching settings
- HATEOAS and pagination configuration options

**Performance Improvements:**
- Async-first architecture for better performance
- Intelligent caching reduces API calls
- Connection pooling for efficient resource usage
- Optimized query processing

#### 🐛 Fixed

- Resolved object ID persistence issues
- Fixed pagination edge cases
- Improved error handling and recovery
- Enhanced SSL/TLS certificate validation
- Corrected filter operator precedence

#### 📚 Documentation

- **New**: [Enhanced Features Guide](docs/ENHANCED_FEATURES.md)
- **New**: [MCP Tools Reference](docs/MCP_TOOLS.md)
- **New**: [Configuration Reference](docs/CONFIGURATION.md)
- **Updated**: [pfSense API Installation Guide](PFSENSE_API_INSTALLATION.md)
- **Updated**: README with community contribution guidelines

#### 🧪 Testing

- Comprehensive test suite for all enhanced features (`test_enhanced_features.py`)
- API integration tests (`test_pfsense_api_v2.py`)
- Feature validation and compatibility testing
- Performance benchmarking tools

#### 🤝 Community

- Added comprehensive community contribution guidelines
- Beta testing program for community validation
- Discord invitation for contributors
- Recognition system for contributors

#### ⚠️ Migration Notes

**From v3.x to v4.0:**
1. Install pfSense REST API v2 package on your pfSense system
2. Generate API key in pfSense User Manager
3. Update environment configuration to use new format
4. Test enhanced features with validation script
5. Update Claude Desktop configuration with new server

**Compatibility:**
- Requires pfSense CE 2.8.0 or pfSense Plus 24.11
- Requires pfSense REST API v2 package installation
- Python 3.8+ required
- FastMCP framework dependency

---

## [3.0.0] - 2024-12-15

### 🚀 FastMCP Integration

#### ✨ Added
- Migrated to FastMCP framework for better MCP compliance
- Improved tool organization and registration
- Enhanced async support throughout the codebase
- Better error handling and response formatting

#### 🔧 Changed
- **Breaking**: Updated tool signatures for FastMCP compatibility
- **Breaking**: Changed import structure for tools
- Improved performance with FastMCP optimizations
- Updated dependencies to include FastMCP

#### 🐛 Fixed
- MCP protocol compliance issues
- Async operation stability
- Tool discovery and registration

#### 📚 Documentation
- Updated README for FastMCP usage
- Added FastMCP-specific configuration examples
- Updated Claude Desktop setup instructions

---

## [2.0.0] - 2024-11-20

### 🚀 Production Ready Release

#### ✨ Added
- Docker deployment support with multi-stage builds
- Production-ready Docker Compose configuration
- Comprehensive security hardening
- Health check endpoints
- Prometheus metrics integration
- Structured logging with JSON output
- Environment-based configuration management

#### 🔧 Changed
- **Breaking**: Updated configuration format
- **Breaking**: Changed default ports and endpoints
- Improved error handling throughout application
- Enhanced logging and monitoring

#### 🛡️ Security
- Added input validation and sanitization
- Implemented rate limiting
- SSL/TLS certificate validation
- Security headers and CORS configuration
- Non-root user in Docker containers

#### 📊 Monitoring
- Health check endpoints (`/health`, `/metrics`)
- Application performance monitoring
- Resource usage tracking
- Audit logging for security events

#### 🐳 Deployment
- Production-ready Docker images
- Docker Compose for easy deployment
- Kubernetes manifests
- Environment-specific configurations

---

## [1.0.0] - 2024-10-15

### 🎉 Initial Release

#### ✨ Added
- Basic Model Context Protocol (MCP) server implementation
- XML-RPC integration with pfSense
- Core MCP tools for pfSense management:
  - `system_status()` - Get system information
  - `list_interfaces()` - Network interface management
  - `get_firewall_rules()` - Firewall rule inspection
  - `create_firewall_rule()` - Basic rule creation
  - `block_ip()` - IP blocking functionality
  - `get_logs()` - Log retrieval
- Claude Desktop integration
- Basic authentication support
- Environment-based configuration

#### 🔐 Access Levels
- READ_ONLY: Monitoring and viewing
- SECURITY_WRITE: Security rule modifications
- ADMIN_WRITE: Full system access
- COMPLIANCE_READ: Audit and compliance
- EMERGENCY_WRITE: Emergency response

#### 📚 Documentation
- Initial README with setup instructions
- Basic configuration guide
- Claude Desktop integration examples
- Permission model documentation

#### 🧪 Testing
- Basic connection testing script
- Simple MCP tool validation
- Manual testing procedures

---

## [Unreleased]

### 🔮 Planned Features

#### High Priority
- GraphQL API integration support
- WebSocket real-time updates
- Multi-pfSense instance management
- Enhanced security analysis tools

#### Community Requests
- Support for additional pfSense packages (Snort, Suricata, HAProxy)
- Advanced backup and restore automation
- Mobile-friendly interface components
- Integration with external SIEM systems

#### Performance Enhancements
- Advanced caching strategies
- Database backend for audit logs
- Performance profiling tools
- Optimized bulk operations

#### Developer Experience
- Web-based configuration UI
- Interactive API documentation
- SDK for custom integrations
- Plugin system for extensions

---

## Version Support Matrix

| Version | pfSense CE | pfSense Plus | Status | EOL Date |
|---------|------------|--------------|--------|----------|
| 4.0.x | 2.8.0+ | 24.11+ | Active | TBD |
| 3.0.x | 2.7.x+ | 23.x+ | Maintenance | 2025-06-01 |
| 2.0.x | 2.6.x+ | 22.x+ | Security Only | 2025-01-01 |
| 1.0.x | 2.5.x+ | 21.x+ | End of Life | 2024-12-31 |

---

## Migration Guides

### Migrating to v4.0.0

**Prerequisites:**
1. pfSense CE 2.8.0 or pfSense Plus 24.11
2. pfSense REST API v2 package installed
3. Python 3.8+

**Steps:**
1. **Install pfSense API Package:**
   ```bash
   # On pfSense system
   pkg-static add https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-2.8.0-pkg-RESTAPI.pkg
   ```

2. **Update Configuration:**
   ```bash
   # Backup old config
   cp .env .env.backup
   
   # Use enhanced template
   cp .env.enhanced .env
   ```

3. **Generate API Key:**
   - Navigate to System → User Manager in pfSense
   - Edit your user and generate an API key
   - Update `PFSENSE_API_KEY` in .env

4. **Test Installation:**
   ```bash
   python test_enhanced_features.py
   ```

5. **Update Claude Desktop:**
   ```json
   {
     "mcpServers": {
       "pfsense-enhanced": {
         "command": "python",
         "args": ["/path/to/main_enhanced_mcp.py"],
         "env": {
           "PFSENSE_URL": "https://your-pfsense.local",
           "PFSENSE_API_KEY": "your-api-key"
         }
       }
     }
   }
   ```

### Migrating from v3.0.0 to v4.0.0

The v4.0.0 release includes breaking changes. See the detailed migration guide above.

### Migrating from v2.0.0 to v3.0.0

Update tool imports and configuration for FastMCP compatibility:

```python
# Old v2.0.0 imports
from main import system_status

# New v3.0.0 imports
from main_fastmcp import system_status
```

---

## Contributing to Changelog

When contributing to this project, please update this changelog with your changes:

1. **Add entries to [Unreleased]** for new features in development
2. **Follow the format**: Use emoji categories (✨ Added, 🔧 Changed, 🐛 Fixed, etc.)
3. **Be descriptive**: Explain the impact and any breaking changes
4. **Include links**: Reference issues and pull requests where relevant
5. **Update version support**: Modify compatibility matrix if needed

### Changelog Categories

- ✨ **Added** for new features
- 🔧 **Changed** for changes in existing functionality  
- 🗑️ **Deprecated** for soon-to-be removed features
- 🐛 **Fixed** for any bug fixes
- 🛡️ **Security** for vulnerability fixes
- 📚 **Documentation** for documentation updates
- 🧪 **Testing** for testing improvements
- 🚀 **Performance** for performance improvements
- 🐳 **Deployment** for deployment and infrastructure changes
- 🤝 **Community** for community-related changes

---

## Release Process

1. **Update version numbers** in relevant files
2. **Update this changelog** with release notes
3. **Tag the release** with semantic version
4. **Create GitHub release** with changelog content
5. **Update documentation** if needed
6. **Notify community** of release

---

*For questions about releases or to report issues, please visit our [GitHub Issues](https://github.com/gensecaihq/pfsense-mcp-server/issues) page.*