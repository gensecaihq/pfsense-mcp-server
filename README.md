# pfSense MCP Server

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/gensecaihq/pfsense-mcp-server/releases/tag/v1.0.0)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MCP 2025-11-25](https://img.shields.io/badge/MCP-2025--11--25-green.svg)](https://modelcontextprotocol.io)
[![pfSense REST API](https://img.shields.io/badge/pfSense%20API-v2.7.3-orange.svg)](https://pfrest.org/)
[![Tests](https://img.shields.io/badge/tests-308%20passing-brightgreen.svg)](#testing)
[![Tools](https://img.shields.io/badge/tools-327-blue.svg)](#what-you-can-do)

> Manage your pfSense firewall with natural language. 327 tools. 9 layers of safety. One command to start.

```
You: "Block all traffic from 203.0.113.5 on WAN"
Claude: Creates block rule → applies changes → confirms with rollback instructions
```

pfSense MCP Server connects [Claude Desktop](https://claude.ai/download), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), and other [MCP](https://modelcontextprotocol.io)-compatible AI clients to your pfSense firewall. Ask questions, diagnose issues, and manage your firewall — all through conversation.

## Why This Exists

Managing a pfSense firewall means clicking through web UI tabs, remembering field names, and hoping you don't fat-finger a rule that locks you out. With this MCP server, you describe what you want in plain English and the AI handles the REST API calls, validates inputs, and warns you before anything destructive happens.

**What makes it different:**
- Every destructive operation requires explicit confirmation and shows you exactly what will happen
- Automatic config backup before every delete/reboot — with a one-line rollback command
- Rate limiting prevents runaway AI loops from flooding your firewall with rules
- Input sanitization blocks command injection, path traversal, and XSS in every parameter

## Quick Start

**Prerequisites:** Python 3.10+, pfSense with [REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) installed

```bash
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set PFSENSE_URL, AUTH_METHOD, and credentials
```

**Connect to Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "pfsense": {
      "command": "python3",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/pfsense-mcp-server",
      "env": {
        "PFSENSE_URL": "https://192.168.1.1",
        "AUTH_METHOD": "basic",
        "PFSENSE_USERNAME": "admin",
        "PFSENSE_PASSWORD": "your-password",
        "PFSENSE_VERSION": "CE_2_8_0",
        "VERIFY_SSL": "false"
      }
    }
  }
}
```

**Start talking to your firewall.** Open Claude Desktop and ask:
- *"Show me all blocked traffic in the last hour"*
- *"What services are running?"*
- *"Create a port forward for port 443 to 192.168.1.50"*
- *"Run a full system health check"*

## What You Can Do

327 tools across every major pfSense subsystem:

| Domain | Tools | What You Can Do |
|---|:---:|---|
| **Firewall Rules** | 9 | Create, update, delete, reorder rules. Bulk block IPs. View compiled pf ruleset. |
| **Aliases** | 5 | Manage host/network/port/URL aliases. Add and remove addresses. |
| **NAT** | 16 | Port forwards, outbound NAT, 1:1 NAT — full lifecycle management. |
| **VPN** | 51 | OpenVPN servers and clients, IPsec tunnels, WireGuard peers — CRUD, status, apply. |
| **Routing** | 16 | Gateways, gateway groups, static routes, default gateway management. |
| **DNS** | 24 | Unbound resolver and dnsmasq forwarder: host overrides, domain overrides, access lists. |
| **DHCP** | 17 | Leases, static mappings, address pools, custom options, server config. |
| **Certificates** | 15 | Certs, CAs, CRLs — generate, renew, export PKCS12. |
| **Users** | 12 | User accounts, groups, LDAP/RADIUS auth server config. |
| **Interfaces** | 14 | Interface config, VLANs, bridges, groups. |
| **System** | 44 | Status, settings, diagnostics, config history, reboot, ping. |
| **Services** | 14 | Start/stop/restart services. NTP, cron, SSH, service watchdog. |
| **Logs** | 3 | Firewall log analysis with parsed IPv4/IPv6 filterlog data. |
| **Traffic Shaping** | 12 | Shapers, queues, and limiters for bandwidth management. |
| **Schedules** | 8 | Time-based firewall rule scheduling. |
| **Virtual IPs** | 5 | CARP, ProxyARP, and IP Alias management. |
| **Troubleshooting** | 10 | Diagnose connectivity, blocked traffic, VPN, DHCP, DNS, HA. Full health report. |
| **Packages** | 43 | HAProxy, ACME/Let's Encrypt, BIND DNS, FreeRADIUS. |
| **Utility** | 9 | HATEOAS navigation, object ID management, guardrail status. |

## Safety First

AI managing a production firewall needs guardrails. This server has 9 layers:

```
"Delete firewall rule 5"

  1. CLASSIFY    → HIGH risk (destructive)
  2. ALLOWLIST   → tool is permitted
  3. SANITIZE    → parameters clean (no injection)
  4. RATE LIMIT  → under 10 deletes/minute
  5. DRY RUN?    → user can preview first
  6. CONFIRM     → blocked until confirm=True
  7. BACKUP      → config revision captured
  8. EXECUTE     → API call made
  9. AUDIT LOG   → action recorded with redacted params

Response includes:
  "config_backup": {
    "pre_change_revision_id": 42,
    "rollback_instruction": "restore_config_backup(revision_id=42, confirm=True)"
  }
```

**Every** destructive operation (52 delete/reboot/halt tools) requires `confirm=True`. **Every** create and update operation (112 tools) is rate-limited and sanitized. **Every** sensitive parameter (passwords, keys, tokens) is redacted in logs and outputs.

You can also:
- Pass `dry_run=True` to preview any destructive operation without executing
- Pass `verify_descr="Allow HTTPS"` to verify you're deleting the right rule (guards against ID shifts)
- Set `MCP_READ_ONLY=true` to expose only 118 read-only tools (search, get, diagnose)
- Set `MCP_ALLOWED_TOOLS=search_firewall_rules,get_firewall_log` to restrict to specific tools

## Supported pfSense Versions

| Version | REST API | Status |
|---|---|---|
| pfSense CE 2.8.1 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases) | Verified |
| pfSense Plus 25.11 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases) | Verified |
| pfSense CE 2.8.0 | v2.6.0+ | Supported |
| pfSense Plus 24.11 | v2.6.0+ | Supported |

Requires the [pfSense REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) by [jaredhendrickson13](https://github.com/jaredhendrickson13).

## Authentication

Three methods supported (configure in `.env`):

| Method | Config | Best For |
|---|---|---|
| **Basic Auth** | `AUTH_METHOD=basic` + username/password | Quick setup, local users |
| **API Key** | `AUTH_METHOD=api_key` + key from System > REST API > Keys | Automation, service accounts |
| **JWT** | `AUTH_METHOD=jwt` + username/password | Short-lived tokens, auto-refresh |

## Deployment Options

**stdio** (default) — for Claude Desktop and Claude Code:
```bash
python3 -m src.main
```

**HTTP** — for remote access and multi-client setups:
```bash
python3 -m src.main -t streamable-http --port 3000
```

**Docker** — hardened container with read-only filesystem:
```bash
docker compose up
```

Container security: non-root user (`mcp:1000`), read-only filesystem, all capabilities dropped, `noexec` tmpfs, `no-new-privileges`.

## Configuration

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `PFSENSE_URL` | Yes | — | pfSense URL (e.g., `https://192.168.1.1`) |
| `AUTH_METHOD` | | `api_key` | `api_key`, `basic`, or `jwt` |
| `PFSENSE_API_KEY` | * | — | REST API key |
| `PFSENSE_USERNAME` | * | — | pfSense username (for basic/jwt) |
| `PFSENSE_PASSWORD` | * | — | pfSense password (for basic/jwt) |
| `PFSENSE_VERSION` | | `CE_2_8_0` | `CE_2_8_0`, `CE_2_8_1`, `CE_26_03`, `PLUS_24_11`, `PLUS_25_11` |
| `VERIFY_SSL` | | `true` | `false` for self-signed certificates |
| `API_TIMEOUT` | | `30` | Request timeout in seconds |
| `MCP_READ_ONLY` | | `false` | Only expose read-only tools |

<details>
<summary>All configuration options</summary>

| Variable | Default | Description |
|---|---|---|
| `ENABLE_HATEOAS` | `false` | Enable HATEOAS links in API responses |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `MCP_HOST` | `127.0.0.1` | Bind address for HTTP mode |
| `MCP_PORT` | `3000` | Port for HTTP mode |
| `MCP_API_KEY` | — | Bearer token for HTTP transport (required) |
| `MCP_ALLOWED_ORIGINS` | localhost | Comma-separated allowed origins |
| `MCP_AUDIT_LOG` | — | Path to audit log file (JSON lines) |
| `MCP_RATE_LIMIT_DELETE` | `10` | Max deletes per 60 seconds |
| `MCP_RATE_LIMIT_CREATE` | `20` | Max creates per 60 seconds |
| `MCP_RATE_LIMIT_CRITICAL` | `2` | Max critical ops per 300 seconds |
| `MCP_ALLOWED_TOOLS` | all | Comma-separated tool allowlist |
| `MCP_ROLLBACK_BUFFER` | `50` | Rollback entries kept in memory |

</details>

## Testing

```bash
python3 -m pytest tests/ -v          # 308 tests
python3 -m pytest tests/ --cov=src   # with coverage
```

## MCP Specification Compliance

Compliant with [MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) (latest):

- `ToolAnnotations` on all 327 tools (readOnlyHint, destructiveHint, idempotentHint)
- `serverInfo.version` and `instructions` provided
- Origin header validation (MUST requirement)
- Bearer token auth with timing-safe comparison
- Default bind to localhost per spec SHOULD
- stdio and Streamable HTTP transports

## Project Structure

```
src/
  main.py              Entry point
  server.py            FastMCP instance + API client
  client.py            pfSense REST API v2 HTTP client
  guardrails.py        9-layer defense-in-depth system
  helpers.py           Validation, parsing, safety guards
  models.py            Data models
  middleware.py        HTTP auth + Origin validation
  tools/               34 tool modules (327 tools)
tests/                 308 tests
```

## Contributing

We need real-world testing across diverse pfSense environments. See [CONTRIBUTING](CONTRIBUTING.md) or:

1. Fork and create a feature branch
2. Run `python3 -m pytest tests/ -v`
3. Submit a PR

**Ideas:** integration tests against real pfSense, additional package support (Snort, Suricata), Ollama local LLM bridge, multi-instance management.

## License

[MIT](LICENSE)

## Acknowledgments

- [jaredhendrickson13](https://github.com/jaredhendrickson13) / [pfrest](https://github.com/pfrest) — pfSense REST API v2 package
- [JeremiahChurch](https://github.com/JeremiahChurch) — modular rewrite (PR #5)
- [shawnpetersen](https://github.com/shawnpetersen) — API v2 endpoint discovery (PR #3)
- [Netgate](https://netgate.com) — pfSense
- [FastMCP](https://gofastmcp.com) — MCP framework
