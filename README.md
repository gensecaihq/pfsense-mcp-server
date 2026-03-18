# pfSense Enhanced MCP Server

[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/gensecaihq-pfsense-mcp-server-badge.png)](https://mseep.ai/app/gensecaihq-pfsense-mcp-server)
[![Version](https://img.shields.io/badge/version-5.0.0-blue.svg)](https://github.com/gensecaihq/pfsense-mcp-server)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)
[![pfSense API](https://img.shields.io/badge/pfSense%20REST%20API-v2.7.3-orange.svg)](https://pfrest.org/)
[![Tests](https://img.shields.io/badge/tests-223%20passing-brightgreen.svg)](#testing)

A Model Context Protocol (MCP) server for managing pfSense firewalls through Claude Desktop, Claude Code, and other MCP-compatible clients. Verified against the pfSense REST API v2 PHP source code for production accuracy.

## Supported pfSense Versions

| pfSense Version | REST API Package | Status |
|---|---|---|
| pfSense CE 2.8.1 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases) | Verified |
| pfSense Plus 25.11 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases) | Verified |
| pfSense CE 2.8.0 | [v2.6.0+](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases) | Supported |
| pfSense Plus 24.11 | [v2.6.0+](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases) | Supported |
| pfSense CE 26.03 | Not yet available | Pending REST API package build |

Requires the [pfSense REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) by jaredhendrickson13.

## Quick Start

### 1. Install pfSense REST API Package

SSH into your pfSense box and install the package for your version:

```bash
# pfSense CE 2.8.1
pkg-static add https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/latest/download/pfSense-2.8.1-pkg-RESTAPI.pkg

# pfSense Plus 25.11
pkg-static -C /dev/null add https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/latest/download/pfSense-25.11-pkg-RESTAPI.pkg
```

Then in the pfSense web UI: **System > REST API** to enable it, and **System > User Manager > [your user]** to generate an API key.

### 2. Setup MCP Server

```bash
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your pfSense URL and API key
```

### 3. Configure Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "pfsense": {
      "command": "python",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/pfsense-mcp-server",
      "env": {
        "PFSENSE_URL": "https://your-pfsense.local",
        "PFSENSE_API_KEY": "your-api-key",
        "PFSENSE_VERSION": "CE_2_8_0",
        "AUTH_METHOD": "api_key",
        "VERIFY_SSL": "true"
      }
    }
  }
}
```

### 4. Start the Server

```bash
# stdio mode (default — for Claude Desktop / Claude Code)
python -m src.main

# HTTP mode (for remote access, requires MCP_API_KEY for bearer auth)
python -m src.main -t streamable-http --port 3000
```

## MCP Tools (41 total)

### Firewall Rules (9 tools)
| Tool | Description |
|---|---|
| `search_firewall_rules` | Search rules with filtering by interface, source IP, port, type, description |
| `find_blocked_rules` | Find all block/reject rules |
| `create_firewall_rule_advanced` | Create rule with position control and validation |
| `update_firewall_rule` | Update an existing rule by ID |
| `delete_firewall_rule` | Delete a rule by ID |
| `move_firewall_rule` | Reorder a rule to a new position |
| `apply_firewall_changes` | Explicitly trigger pf filter reload |
| `bulk_block_ips` | Block multiple IPs with a single apply |
| `get_pf_rules` | Read the compiled pf ruleset (/tmp/rules.debug) |

### Aliases (5 tools)
| Tool | Description |
|---|---|
| `search_aliases` | Search aliases by name, type, or contained IP |
| `create_alias` | Create a new alias (host, network, port, url) |
| `update_alias` | Update an existing alias |
| `delete_alias` | Delete an alias |
| `manage_alias_addresses` | Add or remove addresses from an alias |

### NAT Port Forwards (4 tools)
| Tool | Description |
|---|---|
| `search_nat_port_forwards` | Search port forward rules |
| `create_nat_port_forward` | Create a port forward with validation |
| `update_nat_port_forward` | Update a port forward |
| `delete_nat_port_forward` | Delete a port forward |

### DHCP (7 tools)
| Tool | Description |
|---|---|
| `search_dhcp_leases` | Search active DHCP leases |
| `search_dhcp_static_mappings` | Search static DHCP reservations |
| `create_dhcp_static_mapping` | Create a static mapping |
| `update_dhcp_static_mapping` | Update a static mapping |
| `delete_dhcp_static_mapping` | Delete a static mapping |
| `get_dhcp_server_config` | Get DHCP server configuration |
| `update_dhcp_server_config` | Update DHCP server settings |

### Services (2 tools)
| Tool | Description |
|---|---|
| `search_services` | List services with status filtering |
| `control_service` | Start, stop, or restart a service by name |

### Logs & Monitoring (3 tools)
| Tool | Description |
|---|---|
| `get_firewall_log` | Get firewall log entries (max 50 lines) |
| `analyze_blocked_traffic` | Group blocked traffic by source IP with threat scoring |
| `search_logs_by_ip` | Search logs for a specific IP address |

### System (4 tools)
| Tool | Description |
|---|---|
| `system_status` | Get CPU, memory, disk, and version info |
| `search_interfaces` | Search network interfaces |
| `find_interfaces_by_status` | Find interfaces by status (up/down) |
| `get_arp_table` | Get ARP table (IP-to-MAC mappings) |

### Utility (7 tools)
| Tool | Description |
|---|---|
| `follow_api_link` | Follow a HATEOAS link |
| `enable_hateoas` / `disable_hateoas` | Toggle HATEOAS link inclusion |
| `refresh_object_ids` | Re-query endpoint to get fresh IDs |
| `find_object_by_field` | Look up object by field value |
| `get_api_capabilities` | Get REST API settings |
| `test_enhanced_connection` | Test connection and feature availability |

## API Endpoint Coverage

| Category | Endpoints | Operations |
|---|---|---|
| Firewall Rules | `/firewall/rules`, `/firewall/rule`, `/firewall/apply` | Full CRUD + apply |
| Aliases | `/firewall/aliases`, `/firewall/alias` | Full CRUD + append/remove |
| NAT | `/firewall/nat/port_forwards`, `/firewall/nat/port_forward` | Full CRUD |
| DHCP Leases | `/status/dhcp_server/leases` | Read |
| DHCP Static Mappings | `/services/dhcp_server/static_mappings`, `/services/dhcp_server/static_mapping` | Full CRUD |
| DHCP Server Config | `/services/dhcp_servers`, `/services/dhcp_server` | Read + Update |
| Services | `/status/services`, `/status/service` | Read + Control |
| Firewall Logs | `/status/logs/firewall` | Read (text-based filtering) |
| System Logs | `/status/logs/system`, `/status/logs/dhcp`, `/status/logs/openvpn`, `/status/logs/auth` | Read |
| System Status | `/status/system` | Read |
| Interfaces | `/status/interfaces` | Read |
| ARP Table | `/diagnostics/arp_table` | Read |
| Diagnostics | `/diagnostics/command_prompt` | Execute |
| API Settings | `/system/restapi/settings` | Read |

### Not Yet Implemented

- **Routing** — static routes, gateways, gateway groups
- **VPN** — OpenVPN servers/clients, IPsec, WireGuard
- **DNS** — resolver/forwarder config, host overrides
- **Certificates** — CA, certificate, CSR management
- **Users** — user/group CRUD, LDAP/RADIUS
- **NAT Outbound / 1:1** — outbound NAT rules
- **Advanced** — schedules, traffic shaper, virtual IPs

## Architecture

```
src/
  main.py          Entry point (argparse, connection test, mcp.run())
  server.py        FastMCP instance + API client singleton
  client.py        HTTP client for pfSense REST API v2
  models.py        Enums, dataclasses (QueryFilter, SortOptions, etc.)
  helpers.py       Validation, pagination, safety guards
  middleware.py    Bearer auth middleware for HTTP transport
  tools/
    firewall.py    9 tools
    aliases.py     5 tools
    nat.py         4 tools
    dhcp.py        7 tools
    services.py    2 tools
    logs.py        3 tools
    system.py      4 tools
    utility.py     7 tools
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PFSENSE_URL` | Yes | `https://pfsense.local` | pfSense URL |
| `PFSENSE_API_KEY` | Yes (for api_key auth) | — | REST API key |
| `AUTH_METHOD` | No | `api_key` | `api_key`, `basic`, or `jwt` |
| `PFSENSE_VERSION` | No | `CE_2_8_0` | `CE_2_8_0`, `CE_2_8_1`, `CE_26_03`, `PLUS_24_11`, `PLUS_25_11` |
| `VERIFY_SSL` | No | `true` | Verify SSL certificates |
| `ENABLE_HATEOAS` | No | `false` | Include HATEOAS links in responses |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MCP_TRANSPORT` | No | `stdio` | `stdio` or `streamable-http` |
| `MCP_HOST` | No | `0.0.0.0` | Bind address for HTTP mode |
| `MCP_PORT` | No | `3000` | Port for HTTP mode |
| `MCP_API_KEY` | Required for HTTP mode | — | Bearer token for HTTP transport auth |

## Docker

```bash
# Build
docker build -t pfsense-mcp .

# Run in stdio mode
docker run --rm -e PFSENSE_URL=https://pfsense.local -e PFSENSE_API_KEY=your-key pfsense-mcp

# Run in HTTP mode (docker-compose)
docker compose up
```

The `docker-compose.yml` runs in `streamable-http` mode on port 3000 with bearer auth.

## Testing

```bash
# Run all 223 tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Only tool tests
python -m pytest tests/tools/ -v

# Only client tests
python -m pytest tests/test_api_client.py -v
```

## Safety Guards

- **Page size capped at 200** — prevents pfSense PHP memory exhaustion
- **Log lines capped at 50** — same reason
- **Port format validation** — rejects `"53 853"` which crashes the pf compiler
- **IP validation** — validates addresses before sending to API
- **Log type allowlist** — prevents path traversal via log endpoint
- **Bearer auth required** for HTTP transport mode (fail-closed)
- **Control parameters in JSON body** — verified against pfSense API PHP source

## Known Limitations

- Firewall log API only exposes raw `text` field; per-field filtering is done client-side
- HATEOAS toggle is a global API setting, not per-request (the tools toggle a local session flag)
- pfSense object IDs are non-persistent array indices that change after deletions
- Log retrieval is capped at 50 lines per request to prevent PHP memory exhaustion

## Community & Contributions

### We Need Your Help!

This MCP server has been verified against the pfSense REST API v2 PHP source code, but **real-world testing across diverse pfSense environments is essential**. Whether you're a pfSense veteran, Python developer, or GenAI enthusiast, there are many ways to contribute.

### How You Can Help

**Testing & Feedback**
- Test with your pfSense setup and report what works (and what doesn't)
- Share use cases — tell us how you're using the MCP tools
- Performance feedback across different network sizes

**Bug Reports & Issues**
- [Open an issue](https://github.com/gensecaihq/pfsense-mcp-server/issues) with detailed reproduction steps
- Suggest new MCP tools or API integrations
- Help improve documentation based on real-world usage

**Code Contributions**
- Add tools for missing endpoint categories (VPN, routing, DNS, certificates)
- Add support for pfSense packages (Snort, Suricata, HAProxy)
- Improve test coverage for edge cases
- Performance optimizations

**Documentation**
- Real-world example prompts that work well with Claude
- Integration guides for other MCP clients
- Video tutorials for setup and usage

### Getting Started as a Contributor

1. Fork the repository and create a feature branch
2. Run the test suite: `python -m pytest tests/ -v`
3. Update tests for any new features
4. Submit a pull request with a clear description

### Ideas for Contributions

**High Priority**
- VPN status and configuration tools (OpenVPN, IPsec, WireGuard)
- Routing and gateway management
- DNS resolver/forwarder configuration
- Certificate management

**Medium Priority**
- Support for pfSense packages (Snort, ntopng, FreeRADIUS)
- Multi-pfSense instance management
- GraphQL API integration
- Enhanced log parsing and analysis

### Stay Connected

- **GitHub Issues**: Report bugs and request features
- **Pull Requests**: Contribute code and documentation
- **Releases**: Follow for updates

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [jaredhendrickson13](https://github.com/jaredhendrickson13) / [pfrest](https://github.com/pfrest) for the pfSense REST API v2 package
- [JeremiahChurch](https://github.com/JeremiahChurch) for the production-tested modular rewrite (PR #5, 217 tests)
- [shawnpetersen](https://github.com/shawnpetersen) for discovering the correct API v2 endpoint paths (PR #3)
- [Netgate](https://netgate.com) for pfSense
- [FastMCP](https://gofastmcp.com) for the MCP framework
