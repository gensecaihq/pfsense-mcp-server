# pfSense Enhanced MCP Server

🚀 **A next-generation Model Context Protocol (MCP) server** that enables natural language interaction with pfSense firewalls through Claude Desktop and other GenAI applications. Now with **advanced API features** by pfrest.org including intelligent filtering, HATEOAS navigation, and enterprise-grade controls.



## 🧪 **Community Testing Needed**

> **⚠️ IMPORTANT:** This project needs community testing and validation!  
> **👥 We need your help to test this with real pfSense devices and environments.**
>
> - **🔍 Test it** with your pfSense setup  
> - **🐛 Report issues** via GitHub Issues  
> - **🔧 Fix bugs** and submit PRs  
> - **📝 Improve documentation** based on real-world usage  
> - **💡 Contribute features** and enhancements
>
> **Your testing and contributions will help make this production-ready for everyone!**

[![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)](https://github.com/gensecaihq/pfsense-mcp-server)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)
[![pfSense API](https://img.shields.io/badge/pfSense%20API-v2-orange.svg)](https://pfrest.org/)
[![Community](https://img.shields.io/badge/Community-Welcome-brightgreen.svg)](#-community--contributions)

## ✨ Enhanced Features

### 🎯 **Core Capabilities**
- **🗣️ Natural Language Interface**: Control pfSense using plain English with Claude
- **🔧 Advanced API Integration**: Full support for [jaredhendrickson13/pfsense-api](https://github.com/jaredhendrickson13/pfsense-api) v2
- **🔍 Intelligent Filtering**: 8 filter types (exact, contains, regex, ranges) with multi-field support
- **📊 Smart Pagination**: Efficient handling of large datasets with sorting
- **🔗 HATEOAS Navigation**: Dynamic API exploration with hypermedia controls
- **⚙️ Control Parameters**: Fine-grained operation control (apply, async, placement)
- **🆔 Object ID Management**: Handles dynamic IDs with field-based lookups

### 🏢 **Enterprise Ready**
- **🔒 Multi-Auth Support**: API Key, Basic Auth, JWT with security best practices
- **📈 Production Monitoring**: Health checks, metrics, audit logging
- **🐳 Container Ready**: Docker deployment with security hardening
- **🎨 36 MCP Tools**: Full CRUD for core resources (firewall rules, aliases, NAT, DHCP, services)
- **⚡ High Performance**: Async operations, caching, connection pooling

### 🎮 **Supported pfSense Versions**
| Version | Status | API Package | Features |
|---------|--------|-------------|----------|
| **pfSense CE 2.8.0** | ✅ Fully Supported | [Download](https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-2.8.0-pkg-RESTAPI.pkg) | All enhanced features |
| **pfSense Plus 24.11** | ✅ Fully Supported | [Download](https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-24.11-pkg-RESTAPI.pkg) | All enhanced features |

## 🚀 Quick Start

### 1. Install pfSense REST API Package

**On your pfSense system** (via SSH or console):

```bash
# For pfSense CE 2.8.0
pkg-static add https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-2.8.0-pkg-RESTAPI.pkg

# For pfSense Plus 24.11
pkg-static -C /dev/null add https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-24.11-pkg-RESTAPI.pkg
```

### 2. Configure pfSense API

1. Navigate to **System → REST API** in pfSense webConfigurator
2. Enable the REST API
3. Generate an API key: **System → User Manager → [Your User] → API Keys**
4. Assign appropriate privileges to your API user

### 3. Setup MCP Server

```bash
# Clone the repository
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your pfSense details
```

**Minimal `.env` configuration:**
```bash
PFSENSE_URL=https://your-pfsense.local
PFSENSE_API_KEY=your-api-key-here
PFSENSE_VERSION=CE_2_8_0  # or PLUS_24_11
AUTH_METHOD=api_key
VERIFY_SSL=true
ENABLE_HATEOAS=false  # Set true for navigation links
```

### 4. Test Your Setup

```bash
# Test enhanced features
python tests/test_enhanced_features.py

# Start the enhanced MCP server
python -m src.main
```

### 5. Configure Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "pfsense-enhanced": {
      "command": "python",
      "args": ["/path/to/pfsense-mcp-server/main_enhanced_mcp.py"],
      "env": {
        "PFSENSE_URL": "https://your-pfsense.local",
        "PFSENSE_API_KEY": "your-api-key",
        "PFSENSE_VERSION": "CE_2_8_0",
        "ENABLE_HATEOAS": "false"
      }
    }
  }
}
```

## API Endpoint Coverage

### Firewall Rules

| Endpoint | Operations | MCP Tool(s) | Tested |
|----------|-----------|-------------|--------|
| `/firewall/rules` | Read | `search_firewall_rules`, `find_blocked_rules` | Yes |
| `/firewall/rule` | Create | `create_firewall_rule_advanced`, `bulk_block_ips` | Yes |
| `/firewall/rule` | Update | `update_firewall_rule`, `move_firewall_rule` | Yes |
| `/firewall/rule` | Delete | `delete_firewall_rule` | Yes |

### Firewall Aliases

| Endpoint | Operations | MCP Tool(s) | Tested |
|----------|-----------|-------------|--------|
| `/firewall/aliases` | Read | `search_aliases` | Yes |
| `/firewall/alias` | Create | `create_alias` | Yes |
| `/firewall/alias` | Update | `update_alias`, `manage_alias_addresses` | Yes |
| `/firewall/alias` | Delete | `delete_alias` | Yes |

### NAT Port Forwards

| Endpoint | Operations | MCP Tool(s) | Tested |
|----------|-----------|-------------|--------|
| `/firewall/nat/port_forwards` | Read | `search_nat_port_forwards` | Yes |
| `/firewall/nat/port_forward` | Create | `create_nat_port_forward` | Yes |
| `/firewall/nat/port_forward` | Update | `update_nat_port_forward` | Yes |
| `/firewall/nat/port_forward` | Delete | `delete_nat_port_forward` | Yes |

### Interfaces

| Endpoint | Operations | MCP Tool(s) | Tested |
|----------|-----------|-------------|--------|
| `/status/interfaces` | Read | `search_interfaces`, `find_interfaces_by_status` | Partial |

### Services

| Endpoint | Operations | MCP Tool(s) | Tested |
|----------|-----------|-------------|--------|
| `/status/services` | Read | `search_services` | Yes |
| `/services/start` | Action | `control_service` | Yes |
| `/services/stop` | Action | `control_service` | Yes |
| `/services/restart` | Action | `control_service` | Yes |

### DHCP

| Endpoint | Operations | MCP Tool(s) | Tested |
|----------|-----------|-------------|--------|
| `/status/dhcp_server/leases` | Read | `search_dhcp_leases` | Yes |
| `/services/dhcp_server/static_mappings` | Read | `search_dhcp_static_mappings` | Yes |
| `/services/dhcp_server/static_mapping` | Create | `create_dhcp_static_mapping` | Yes |
| `/services/dhcp_server/static_mapping` | Update | `update_dhcp_static_mapping` | Yes |
| `/services/dhcp_server/static_mapping` | Delete | `delete_dhcp_static_mapping` | Yes |

### Logs & Monitoring

| Endpoint | Operations | MCP Tool(s) | Tested |
|----------|-----------|-------------|--------|
| `/status/logs/firewall` | Read | `get_firewall_log`, `analyze_blocked_traffic`, `search_logs_by_ip` | Partial |
| `/status/system` | Read | `system_status` | Yes |

### System & API

| Endpoint | Operations | MCP Tool(s) | Tested |
|----------|-----------|-------------|--------|
| `/system/restapi/settings` | Read | `get_api_capabilities` | Partial |
| HATEOAS links | Navigation | `follow_api_link`, `enable_hateoas`, `disable_hateoas` | Partial |
| Dynamic endpoints | Lookup | `refresh_object_ids`, `find_object_by_field` | Partial |
| Connection test | Diagnostic | `test_enhanced_connection` | Partial |

### Not Yet Implemented

Major pfSense API v2 endpoint categories not yet covered:

- **Routing** -- static routes, gateways, gateway groups (`/routing/*`)
- **VPN** -- OpenVPN servers/clients, IPSec phases, WireGuard tunnels/peers (`/vpn/*`)
- **DNS** -- resolver/forwarder config, host overrides (`/services/dns_resolver/*`, `/services/dns_forwarder/*`)
- **Certificates** -- CA, CRT, CSR management (`/certificates/*`)
- **Users & Auth** -- user/group CRUD, LDAP/RADIUS config (`/users/*`, `/auth/*`)
- **NAT Outbound / 1:1** -- outbound NAT rules, 1:1 NAT (`/firewall/nat/outbound`, `/firewall/nat/1to1`)
- **Advanced Firewall** -- schedules, traffic shaper, virtual IPs, connection states
- **Interface Config** -- VLANs, bridges, LAGs, individual interface settings
- **Other Logs** -- system, DHCP, VPN, captive portal logs
- **Diagnostics** -- ARP table, routing table, DNS lookups, command execution

## 💬 Enhanced Example Prompts

```
"Search for firewall rules on WAN interface blocking port 22"
"Show me blocked traffic patterns from the last 24 hours"
"Find all aliases containing IP 192.168.1.100"
"Block these suspicious IPs: 198.51.100.1, 203.0.113.1"
"Search DHCP leases for hostname containing 'server'"
"Move firewall rule ID 5 to position 1"
"Analyze blocked traffic and group by source IP"
"Find interfaces that are currently down"
"Search for firewall rules with 'malware' in description"
"Show me the top 10 blocked source IPs"
```

## 📚 Documentation

### 📖 **Setup Guides**
- **[pfSense API Installation Guide](PFSENSE_API_INSTALLATION.md)** - Complete setup instructions
- **[Enhanced Features Guide](docs/ENHANCED_FEATURES.md)** - Advanced capabilities overview
- **[Configuration Reference](docs/CONFIGURATION.md)** - All environment variables

### 🔧 **Technical Documentation**
- **[API Integration Details](docs/API_INTEGRATION.md)** - How the enhanced API works
- **[MCP Tools Reference](docs/MCP_TOOLS.md)** - Complete tool documentation
- **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### 🚀 **Deployment**
- **[Docker Deployment](docs/DOCKER_DEPLOYMENT.md)** - Container setup
- **[Production Guide](docs/PRODUCTION.md)** - Enterprise deployment
- **[Security Best Practices](docs/SECURITY.md)** - Hardening guidelines

## 🧪 Testing

```bash
# Run the full test suite (114 tests)
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Run only MCP tool tests
pytest tests/test_main.py -v

# Run only API client tests
pytest tests/test_api_client.py -v

# Test live connection to pfSense (requires .env configured)
python tests/test_enhanced_features.py
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Claude Desktop │────│ Enhanced MCP     │────│ pfSense API v2  │
│   (Natural Lang) │    │ Server (Python)  │    │ (REST/GraphQL)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ Advanced Features │    │ pfSense System  │
                       │ • Filtering       │    │ • Firewall      │
                       │ • Pagination      │    │ • Interfaces    │
                       │ • HATEOAS         │    │ • Services      │
                       │ • Object IDs      │    │ • DHCP/VPN      │
                       └──────────────────┘    └─────────────────┘
```

## 🤝 Community & Contributions

### 🌟 **We Need Your Help!**

This MCP server represents a significant advancement in pfSense automation, but **we need the community to help make it even better**! Whether you're a pfSense veteran, Python developer, or GenAI enthusiast, there are many ways to contribute.

### 🎯 **How You Can Help**

#### 🧪 **Beta Testing & Feedback**
- **Test in your environment**: Try the enhanced MCP server with your pfSense setup
- **Report compatibility**: Let us know what works (and what doesn't) with different pfSense versions
- **Share use cases**: Tell us how you're using the MCP tools in real scenarios
- **Performance feedback**: Help us optimize for different network sizes and configurations

#### 🐛 **Bug Reports & Issues**
- **Found a bug?** [Open an issue](https://github.com/gensecaihq/pfsense-mcp-server/issues) with detailed reproduction steps
- **Missing feature?** Suggest new MCP tools or API integrations
- **Documentation unclear?** Help us improve the guides and examples

#### 💻 **Code Contributions**
- **New MCP tools**: Add tools for pfSense packages (HAProxy, Suricata, etc.)
- **Enhanced filtering**: Improve search and discovery capabilities
- **Performance optimizations**: Help make the server faster and more efficient
- **Test coverage**: Add comprehensive tests for edge cases

#### 📚 **Documentation & Examples**
- **Real-world examples**: Share Claude prompts that work well
- **Integration guides**: How to use with other tools and workflows  
- **Video tutorials**: Create setup and usage demonstrations
- **Translation**: Help make documentation accessible in other languages

### 🚀 **Getting Started as a Contributor**

1. **🍴 Fork the repository** and create a feature branch
2. **🧪 Test your changes** with the comprehensive test suite
3. **📝 Update documentation** for any new features
4. **🔄 Submit a pull request** with a clear description

### 💡 **Ideas for Contributions**

#### 🎯 **High Priority**
- Support for additional pfSense packages (Snort, ntopng, FreeRADIUS)
- Enhanced security analysis tools
- Backup and restore automation
- Multi-pfSense instance management

#### 🔧 **Technical Improvements**
- GraphQL API integration
- WebSocket real-time updates
- Advanced caching strategies
- Performance profiling tools

#### 🎨 **User Experience**
- Natural language query improvements
- Claude Desktop interface enhancements
- Web-based configuration UI
- Mobile-friendly tools

### 🏆 **Recognition**

Contributors will be:
- **Listed in our contributors section**
- **Credited in release notes**
- **Given priority support** for their own deployments
- **Invited to the contributor Discord** for direct collaboration

### 📢 **Stay Connected**

- **GitHub Discussions**: Share ideas and ask questions
- **Issues**: Report bugs and request features  
- **Pull Requests**: Contribute code and documentation
- **Releases**: Follow for updates and new features

**Together, we can make pfSense automation accessible to everyone through natural language! 🌟**

---

*"The best open source projects are built by communities, not individuals. Your contribution, no matter how small, makes a difference!"*

## 🔒 Security Considerations

- **🔐 Authentication**: Multi-method support with privilege checking
- **🛡️ Input Validation**: All user inputs validated and sanitized
- **🔍 Audit Logging**: Comprehensive activity tracking
- **🚫 Rate Limiting**: Protection against abuse
- **🔒 SSL/TLS**: Encrypted communication enforced
- **👤 Privilege Management**: Role-based access control

## 📈 Performance & Scalability

- **⚡ Async Operations**: Non-blocking I/O for better performance
- **💾 Intelligent Caching**: Reduce API calls with smart caching
- **🔄 Connection Pooling**: Efficient resource utilization
- **📊 Pagination**: Handle large datasets efficiently
- **🎯 Targeted Queries**: Advanced filtering reduces data transfer
- **📈 Metrics**: Built-in monitoring and performance tracking

## 🆘 Support & Troubleshooting

### Common Issues

1. **Connection Failed**: Check pfSense API package installation
2. **Authentication Error**: Verify API key and user privileges  
3. **Permission Denied**: Ensure user has required pfSense privileges
4. **Filter Not Working**: Check filter syntax and field names
5. **Slow Performance**: Enable caching and optimize queries

### Getting Help

- **📖 Documentation**: Check our comprehensive guides
- **🐛 Issues**: Search existing issues or create a new one
- **💬 Discussions**: Ask questions in GitHub Discussions
- **📧 Support**: Community support through GitHub

## 📝 Changelog

### v4.0.0 - Enhanced API Integration
- ✨ Full pfSense REST API v2 support
- 🔍 Advanced filtering with 8 operators
- 📊 Smart pagination and sorting
- 🔗 HATEOAS navigation support
- ⚙️ Control parameters implementation
- 🆔 Dynamic object ID management
- 🛠️ 36 MCP tools with full CRUD for core resources
- 📚 Comprehensive documentation

### v3.0.0 - FastMCP Integration
- 🚀 Migrated to FastMCP framework
- 🔧 Improved tool organization
- 📈 Better performance and reliability

### v2.0.0 - Production Ready
- 🐳 Docker deployment support
- 🔒 Security hardening
- 📊 Monitoring and metrics

### v1.0.0 - Initial Release
- 🎯 Basic MCP functionality
- 🔌 XML-RPC integration
- 🛠️ Core pfSense tools

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **[jaredhendrickson13](https://github.com/jaredhendrickson13)** for the excellent pfSense REST API package
- **[Anthropic](https://anthropic.com)** for the Model Context Protocol and Claude
- **[Netgate](https://netgate.com)** for pfSense
- **[FastMCP](https://github.com/jlowin/fastmcp)** for the MCP framework
- **Community contributors** for testing, feedback, and improvements

---

<div align="center">

**⭐ Star this repo if it helps you manage pfSense with AI! ⭐**

Made with ❤️ by the community, for the community

</div>
