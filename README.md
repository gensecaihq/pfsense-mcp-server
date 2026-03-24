# pfSense Enhanced MCP Server

[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/gensecaihq-pfsense-mcp-server-badge.png)](https://mseep.ai/app/gensecaihq-pfsense-mcp-server)
[![Version](https://img.shields.io/badge/version-5.0.0-blue.svg)](https://github.com/gensecaihq/pfsense-mcp-server)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)
[![pfSense API](https://img.shields.io/badge/pfSense%20REST%20API-v2.7.3-orange.svg)](https://pfrest.org/)
[![Tests](https://img.shields.io/badge/tests-308%20passing-brightgreen.svg)](#testing)
[![Tools](https://img.shields.io/badge/MCP%20tools-315-blue.svg)](#mcp-tools-315-total)

A Model Context Protocol (MCP) server for managing pfSense firewalls through Claude Desktop, Claude Code, and other MCP-compatible clients. Verified against the pfSense REST API v2 PHP source code for production accuracy. Full defense-in-depth guardrail system for destructive operations.

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

Then in the pfSense web UI, navigate to **System > REST API** to enable and configure the API.

#### Authentication Setup

The REST API supports three authentication methods (multiple can be enabled simultaneously). Configure which methods are active on the **System > REST API** settings page.

**Option A: Basic Auth (simplest — uses your existing pfSense credentials)**
No additional setup needed. Uses your pfSense local database username and password. Note: LDAP/RADIUS backends are not supported — only local database users.

**Option B: API Key**
Go to **System > REST API > Keys** to generate an API key. The key is tied to the user who creates it and inherits that user's privileges. Keys can also be generated via `POST /api/v2/auth/key`.

**Option C: JWT**
Uses your pfSense local database credentials to obtain a short-lived token (default: 1 hour) via `POST /api/v2/auth/jwt`. The MCP server handles token retrieval and refresh automatically. The token is validated on refresh — if the API returns a malformed response, startup fails with a clear error instead of silently sending invalid credentials.

See the [pfSense REST API Installation Guide](PFSENSE_API_INSTALLATION.md) for detailed instructions.

### 2. Setup MCP Server

```bash
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your pfSense connection details (see Environment Variables below)
```

### 3. Configure Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

**Using Basic Auth (recommended for quick setup):**

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

**Using API Key:**

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
        "AUTH_METHOD": "api_key",
        "PFSENSE_VERSION": "CE_2_8_0",
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

On startup, the server tests the connection to pfSense and reports specific error details on failure (authentication errors, SSL issues, unreachable host, missing API package).

## MCP Tools (315 total)

### Firewall (34 tools)

| Category | Tools | Description |
|---|---|---|
| **Rules** (9) | `search_firewall_rules`, `find_blocked_rules`, `create_firewall_rule_advanced`, `update_firewall_rule`, `delete_firewall_rule`, `move_firewall_rule`, `apply_firewall_changes`, `bulk_block_ips`, `get_pf_rules` | Full CRUD with position control, rollback, stale-ID guard (`verify_descr`), bulk blocking |
| **Aliases** (5) | `search_aliases`, `create_alias`, `update_alias`, `delete_alias`, `manage_alias_addresses` | CRUD + append/remove addresses, alias type validation |
| **Schedules** (8) | `search_firewall_schedules`, `create_firewall_schedule`, `update_firewall_schedule`, `delete_firewall_schedule`, `search_schedule_time_ranges`, `create_schedule_time_range`, `update_schedule_time_range`, `delete_schedule_time_range` | Time-based rule scheduling |
| **States** (4) | `search_firewall_states`, `delete_firewall_state`, `get_firewall_state_size`, `get_firewall_advanced_settings` | State table management |
| **Virtual IPs** (5) | `search_virtual_ips`, `create_virtual_ip`, `update_virtual_ip`, `delete_virtual_ip`, `apply_virtual_ip_changes` | CARP, ProxyARP, IP Alias |
| **Traffic Shaping** (12) | Shapers, queues, limiters — full CRUD for each | Bandwidth management |

### NAT (16 tools)

| Category | Tools |
|---|---|
| **Port Forwards** (4) | `search_nat_port_forwards`, `create_nat_port_forward`, `update_nat_port_forward`, `delete_nat_port_forward` |
| **Outbound NAT** (7) | `search_nat_outbound_mappings`, `create_nat_outbound_mapping`, `update_nat_outbound_mapping`, `delete_nat_outbound_mapping`, `get_nat_outbound_mode`, `update_nat_outbound_mode`, `apply_nat_changes` |
| **1:1 NAT** (5) | `search_nat_onetoone_mappings`, `create_nat_onetoone_mapping`, `update_nat_onetoone_mapping`, `delete_nat_onetoone_mapping`, `apply_nat_onetoone_changes` |

### VPN (51 tools)

| Category | Tools |
|---|---|
| **OpenVPN** (12) | Server/client CRUD, CSO management, status, client config export |
| **IPsec** (14) | Phase 1/Phase 2 CRUD, encryption CRUD, apply, SA status |
| **WireGuard** (13) | Tunnel/peer CRUD, allowed IPs, settings, apply |
| **VPN Advanced** (12) | Phase 2 encryption, tunnel addresses, OpenVPN detailed status/connections |

### Routing (16 tools)
Gateways CRUD, gateway groups CRUD, static routes CRUD, default gateway, apply, gateway status

### DNS (24 tools)

| Category | Tools |
|---|---|
| **DNS Resolver** (16) | Host/domain overrides CRUD, access lists CRUD, settings, apply |
| **DNS Forwarder** (8) | Host overrides CRUD, host override aliases, apply |

### DHCP (17 tools)

| Category | Tools |
|---|---|
| **Core** (7) | Leases, static mappings CRUD, server config |
| **Advanced** (10) | Address pools CRUD, custom options CRUD, apply, backend selection |

### Certificates/PKI (15 tools)
Certificates CRUD + generate/renew/PKCS12 export, Certificate Authorities CRUD, CRLs CRUD

### Users & Auth (12 tools)
Users CRUD, groups CRUD, auth servers CRUD

### Interfaces (14 tools)
Interface config CRUD, VLANs CRUD, bridges, groups, available interfaces, apply

### System & Diagnostics (34 tools)

| Category | Tools |
|---|---|
| **System Status** (4) | `system_status`, `search_interfaces`, `find_interfaces_by_status`, `get_arp_table` |
| **System Settings** (12) | DNS, hostname, tunables CRUD, packages, CARP status, version |
| **Advanced Settings** (14) | Timezone, console, WebGUI, email notifications, log settings, DHCP relay, firewall advanced, state size |
| **Diagnostics** (8) | Ping, reboot, halt, config history, pf tables |

### Services (14 tools)

| Category | Tools |
|---|---|
| **Core** (2) | `search_services`, `control_service` |
| **Misc** (12) | NTP settings/servers, cron jobs, service watchdog, SSH settings, Wake-on-LAN |

### Logs (3 tools)
`get_firewall_log`, `analyze_blocked_traffic`, `search_logs_by_ip` — with parsed filterlog CSV for IPv4/IPv6

### Package Tools (43 tools)

| Package | Tools |
|---|---|
| **HAProxy** (15) | Backends, frontends, servers, files, settings, apply |
| **ACME/Let's Encrypt** (10) | Certificates, account keys, issue/renew |
| **BIND DNS** (10) | Zones, records, access lists, settings |
| **FreeRADIUS** (8) | Users, clients CRUD |

### Utility (9 tools)
`follow_api_link`, `enable_hateoas`, `disable_hateoas`, `refresh_object_ids`, `find_object_by_field`, `get_api_capabilities`, `test_enhanced_connection`, `get_guardrail_status`, `check_tool_risk`

## Defense-in-Depth Security (src/guardrails.py)

The guardrail system implements 8 layers of protection for destructive operations, following security best practices for AI-driven infrastructure management.

### 1. Action Classification (5 Risk Levels)

Every tool is automatically classified by risk level:

| Level | Tools | Behavior |
|---|---|---|
| **READ** | `search_*`, `get_*`, `find_*`, `analyze_*` | No restrictions |
| **LOW** | `update_*`, `apply_*`, `enable_*`, `disable_*` | Rate-limited |
| **MEDIUM** | `create_*`, `move_*`, `manage_*` | Rate-limited + input sanitization |
| **HIGH** | `delete_*`, `disconnect_*` | Requires `confirm=True` + rate-limited |
| **CRITICAL** | `halt_system`, `reboot_system`, `bulk_block_ips` | Requires `confirm=True` + strict rate limit |

### 2. Mandatory Approval Gate

All HIGH and CRITICAL operations require explicit `confirm=True`. Without it, the tool returns a full visualization of what the operation would do, including impact summary and redacted parameters.

### 3. Input Sanitization

All string parameters are recursively scanned for injection patterns:
- Directory traversal (`../`)
- Command injection (`;`, `|`, `` ` ``, `$()`, `${}`)
- XSS (`<script>`)
- Nested dicts and list items are recursively checked

### 4. Rate Limiting

Sliding-window rate limits prevent runaway automation:

| Category | Default Limit | Env Var |
|---|---|---|
| Create operations | 20 per 60s | `MCP_RATE_LIMIT_CREATE` |
| Delete operations | 10 per 60s | `MCP_RATE_LIMIT_DELETE` |
| Critical operations | 2 per 300s | `MCP_RATE_LIMIT_CRITICAL` |

### 5. Audit Logging

Every destructive action is logged in JSON lines format with tool name, risk level, redacted parameters, and result. Configure via `MCP_AUDIT_LOG` env var.

### 6. Dry-Run Mode

Any destructive tool can be previewed without executing by passing `dry_run=True`. Returns impact summary without making changes.

### 7. Sensitive Data Redaction

Passwords, keys, tokens, secrets, and certificates are automatically redacted (`***REDACTED***`) in approval requests, audit logs, and error messages. Redaction recurses into nested dicts and lists.

### 8. Command Allowlisting

Optional `MCP_ALLOWED_TOOLS` env var restricts which tools can execute destructive actions. Read-only tools are always allowed.

### Additional Safety

| Feature | Description |
|---|---|
| **Stale-ID guard** | `verify_descr` param on firewall update/delete cross-checks before operating |
| **Rollback** | Create+move failure auto-deletes the created rule |
| **Bulk warnings** | Apply failure reports pending rule IDs for manual cleanup |
| **ID shift notes** | Every delete response warns that object IDs have shifted |
| **Port validation** | Rejects `"53 853"` (crashes pf compiler), validates 1-65535 |
| **MAC normalization** | Accepts colon/hyphen/bare formats, normalizes to lowercase colon |
| **Description cap** | Control characters stripped, length capped at 1024 |
| **Log type allowlist** | Prevents path traversal via log endpoint |
| **Pagination cap** | Page 500 max, offset 100k max to prevent PHP memory exhaustion |
| **Diagnostic allowlist** | Exact-match frozenset for command execution |
| **Origin validation** | HTTP transport validates Origin header per MCP spec |
| **Bearer auth** | Timing-safe `hmac.compare_digest` for HTTP transport |

### Runtime Guardrail Tools

| Tool | Description |
|---|---|
| `get_guardrail_status` | View current guardrail config, rate limits, and recent rollback history |
| `check_tool_risk` | Check risk classification and requirements for any tool |

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
| Firewall Logs | `/status/logs/firewall` | Read (parsed field-level filtering) |
| System Logs | `/status/logs/system`, `/status/logs/dhcp`, `/status/logs/openvpn`, `/status/logs/auth` | Read |
| System Status | `/status/system` | Read |
| Interfaces | `/status/interfaces` | Read |
| ARP Table | `/diagnostics/arp_table` | Read |
| Diagnostics | `/diagnostics/command_prompt` | Execute (allowlisted commands only) |
| API Settings | `/system/restapi/settings` | Read + Update (HATEOAS toggle) |
| VPN - OpenVPN | `/vpn/openvpn/server`, `/vpn/openvpn/client`, `/vpn/openvpn/cso` | Full CRUD + status + export |
| VPN - IPsec | `/vpn/ipsec/phase1`, `/vpn/ipsec/phase2`, `/vpn/ipsec/apply` | Full CRUD + encryption + apply |
| VPN - WireGuard | `/vpn/wireguard/tunnel`, `/vpn/wireguard/peer`, `/vpn/wireguard/apply` | Full CRUD + settings + apply |
| Routing | `/routing/gateway`, `/routing/static_route`, `/routing/apply` | Full CRUD + groups + apply |
| DNS Resolver | `/services/dns_resolver/*` | Host/domain overrides, access lists, settings, apply |
| DNS Forwarder | `/services/dns_forwarder/*` | Host overrides, aliases, apply |
| Certificates | `/system/certificate`, `/system/certificate_authority`, `/system/crl` | Full CRUD + generate/renew/export |
| Users | `/user`, `/user/group`, `/user/auth_server` | Full CRUD |
| Interfaces | `/interface`, `/interface/vlan`, `/interface/bridge`, `/interface/group` | Full CRUD + apply |
| NAT Outbound | `/firewall/nat/outbound/*` | Mappings CRUD + mode |
| NAT 1:1 | `/firewall/nat/one_to_one/*` | Mappings CRUD |
| Schedules | `/firewall/schedule`, `/firewall/schedule/time_range` | Full CRUD |
| Virtual IPs | `/firewall/virtual_ip`, `/firewall/virtual_ip/apply` | Full CRUD + apply |
| Traffic Shaping | `/firewall/traffic_shaper`, `traffic_shaper/limiter` | Shapers, queues, limiters |
| System Settings | `/system/dns`, `/system/hostname`, `/system/tunable` | Read + Update |
| Diagnostics | `/diagnostics/ping`, `/diagnostics/reboot`, `/diagnostics/config_history` | Execute + Read |
| HAProxy | `/services/haproxy/*` | Backends, frontends, servers, settings, apply |
| ACME | `/services/acme/*` | Certificates, account keys, issue/renew |
| BIND DNS | `/services/bind/*` | Zones, records, access lists, settings |
| FreeRADIUS | `/services/freeradius/*` | Users, clients CRUD |
| Misc Services | `/services/ntp`, `/services/cron`, `/services/ssh`, `/services/wake_on_lan` | Settings + CRUD |

## Architecture

```
src/
  main.py              Entry point (argparse, connection test, mcp.run())
  server.py            FastMCP instance + API client singleton
  client.py            HTTP client with generic CRUD for pfSense REST API v2
  guardrails.py        Defense-in-depth: classification, rate limits, sanitization, audit
  models.py            Enums, dataclasses (QueryFilter, SortOptions, ControlParameters)
  helpers.py           Validation, pagination, filterlog parser, safety guards
  middleware.py        Bearer auth + Origin validation middleware for HTTP transport
  tools/
    firewall.py        9 tools  — rules CRUD, apply, bulk block, pf rules
    aliases.py         5 tools  — alias CRUD, address management
    nat.py             4 tools  — port forwards CRUD
    nat_outbound.py    7 tools  — outbound NAT mappings, mode
    nat_onetoone.py    5 tools  — 1:1 NAT mappings
    dhcp.py            7 tools  — leases, static mappings, server config
    dhcp_advanced.py   10 tools — address pools, custom options, apply, backend
    services.py        2 tools  — service list, start/stop/restart
    logs.py            3 tools  — firewall logs, blocked traffic analysis
    system.py          4 tools  — status, interfaces, ARP table
    system_settings.py 12 tools — DNS, hostname, tunables, packages, CARP
    system_advanced.py 14 tools — timezone, console, webgui, email, log settings
    diagnostics.py     8 tools  — ping, reboot, halt, config history, pf tables
    routing.py         16 tools — gateways, groups, static routes, default GW, apply
    dns_resolver.py    16 tools — host/domain overrides, access lists, settings, apply
    dns_forwarder.py   8 tools  — host overrides, aliases, apply
    certificates.py    15 tools — certs, CAs, CRLs, generate, renew, PKCS12
    users.py           12 tools — users, groups, auth servers
    interfaces.py      14 tools — config, VLANs, bridges, groups, apply
    firewall_schedules.py  8 tools — schedules, time ranges
    firewall_states.py     4 tools — states, state size, advanced settings
    virtual_ips.py     5 tools  — CARP, ProxyARP, IP Alias, apply
    traffic_shaper.py  12 tools — shapers, queues, limiters
    vpn_openvpn.py     12 tools — server/client CRUD, CSO, status, export
    vpn_ipsec.py       14 tools — phase1/phase2, encryption, apply, SA status
    vpn_wireguard.py   13 tools — tunnel/peer CRUD, allowed IPs, settings, apply
    vpn_advanced.py    12 tools — phase2 encryption, tunnel addresses, status
    utility.py         9 tools  — HATEOAS, object IDs, guardrail status
    pkg_haproxy.py     15 tools — backends, frontends, servers, files, apply
    pkg_acme.py        10 tools — certificates, account keys, issue/renew
    pkg_bind.py        10 tools — zones, records, access lists, settings
    pkg_freeradius.py  8 tools  — users, clients CRUD
    misc_services.py   12 tools — NTP, cron, watchdog, SSH, WoL
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `PFSENSE_URL` | Yes | — | pfSense URL (e.g., `https://192.168.1.1`) |
| `AUTH_METHOD` | No | `api_key` | `api_key`, `basic`, or `jwt` |
| `PFSENSE_API_KEY` | Yes (for `api_key` auth) | — | REST API key (generate at System > REST API > Keys) |
| `PFSENSE_USERNAME` | Yes (for `basic`/`jwt` auth) | — | pfSense local database username |
| `PFSENSE_PASSWORD` | Yes (for `basic`/`jwt` auth) | — | pfSense local database password |
| `PFSENSE_VERSION` | No | `CE_2_8_0` | Must be one of: `CE_2_8_0`, `CE_2_8_1`, `CE_26_03`, `PLUS_24_11`, `PLUS_25_11`. Unrecognized values cause a startup error. |
| `VERIFY_SSL` | No | `true` | Verify SSL certificates (`false` for self-signed certs) |
| `API_TIMEOUT` | No | `30` | API request timeout in seconds (increase for slow hardware or large rulesets) |
| `ENABLE_HATEOAS` | No | `false` | Initial HATEOAS state (can be toggled at runtime via tools) |
| `LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MCP_TRANSPORT` | No | `stdio` | `stdio` or `streamable-http` |
| `MCP_HOST` | No | `127.0.0.1` | Bind address for HTTP mode (use `0.0.0.0` for remote access) |
| `MCP_PORT` | No | `3000` | Port for HTTP mode |
| `MCP_API_KEY` | Required for HTTP mode | — | Bearer token for HTTP transport auth |
| `MCP_ALLOWED_ORIGINS` | No | localhost only | Comma-separated allowed origins for HTTP transport |
| `MCP_AUDIT_LOG` | No | disabled | Path to audit log file (JSON lines format) |
| `MCP_RATE_LIMIT_DELETE` | No | `10` | Max delete operations per 60s |
| `MCP_RATE_LIMIT_CREATE` | No | `20` | Max create operations per 60s |
| `MCP_RATE_LIMIT_CRITICAL` | No | `2` | Max critical operations (reboot/halt) per 300s |
| `MCP_ALLOWED_TOOLS` | No | all | Comma-separated allowlist of permitted destructive tools |
| `MCP_ROLLBACK_BUFFER` | No | `50` | Number of rollback entries to keep in memory |

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
# Run all 308 tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Only tool tests
python -m pytest tests/tools/ -v

# Only client tests
python -m pytest tests/test_api_client.py -v

# Only helper tests (validation, parsing)
python -m pytest tests/test_helpers.py -v

# Only guardrail tests
python -m pytest tests/test_guardrails.py -v
```

## Known Limitations

- **Firewall logs**: API only exposes a raw `text` field — the server parses filterlog CSV by field position for structured filtering, with regex fallback. Format changes across pfSense versions could affect IP extraction (extracted IPs are validated).
- **HATEOAS**: Global pfSense REST API setting — `enable_hateoas`/`disable_hateoas` affect all API consumers, not just this session.
- **Object IDs**: Non-persistent array indices that shift after deletions — use `verify_descr`, `find_object_by_field`, or `refresh_object_ids` for safety.
- **Log lines**: Capped at 50 per request to prevent PHP memory exhaustion.
- **Package tools**: HAProxy, BIND, ACME, and FreeRADIUS tools require the corresponding pfSense packages to be installed. Tools are always loaded but will return API errors if the package is absent.
- **Bulk operations**: PUT (replace all) and DELETE (delete all) on plural endpoints are intentionally not exposed to prevent accidental config wipes.

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
