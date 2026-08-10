<div align="center">

# 🛡️ pfSense MCP Server

### Manage your pfSense firewall in plain English — from Claude Desktop, Claude Code, or any MCP client.

**333 tools** across every subsystem · **wire-format verified** against the pfSense REST API · **safety guardrails** on every change

<br>

[![CI](https://github.com/gensecaihq/pfsense-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/gensecaihq/pfsense-mcp-server/actions/workflows/ci.yml)
[![MCP 2025-11-25](https://img.shields.io/badge/MCP-2025--11--25-6E56CF.svg)](https://modelcontextprotocol.io)
[![pfSense API v2.10.0](https://img.shields.io/badge/pfSense%20API-v2.10.0-orange.svg)](https://pfrest.org/)
[![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-481%20passing-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

</div>

---

```text
You:     Block all traffic from 203.0.113.5 on WAN
Claude:  ✓ created block rule  →  ✓ applied changes  →  rollback: restore_config_backup(revision_id=42)

You:     Why can't 192.168.1.50 reach the internet?
Claude:  ran diagnostics → gateway WAN_DHCP is down, and a block rule on LAN matches this host

You:     Add a WireGuard peer for my laptop and show me the config
Claude:  ✓ created peer on tun_wg0  →  here's the client config to import
```

**pfSense MCP Server** connects [Claude Desktop](https://claude.ai/download), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), and any other [MCP](https://modelcontextprotocol.io) client to your pfSense firewall. Ask questions, diagnose issues, and change configuration through conversation — with a confirmation gate, config backup, and rollback on every destructive action.

Letting an AI touch a production firewall is only safe if the plumbing is right, so that's where the work went: every tool's wire format is verified against the pfSense REST API schema by a contract-test layer, and every change runs through a guardrail pipeline. 481 tests, CI on Python 3.11–3.13.

> [!TIP]
> Jump to the [Quick Start](#quick-start) — about two minutes with `uvx`, no clone required. And if this saves you a trip through the pfSense web UI, a ⭐ helps others find it.

## Contents

[Why this exists](#why-this-exists) ·
[Quick start](#quick-start) ·
[What you can do](#what-you-can-do) ·
[Safety](#safety-first) ·
[Supported versions](#supported-pfsense-versions) ·
[Authentication](#authentication) ·
[Deployment](#deployment-options) ·
[Configuration](#configuration) ·
[Testing](#testing) ·
[MCP compliance](#mcp-specification-compliance) ·
[Architecture](ARCHITECTURE.md) ·
[Contributing](CONTRIBUTING.md)

## Why This Exists

Managing a pfSense firewall means clicking through web UI tabs, remembering field names, and hoping you don't fat-finger a rule that locks you out. With this MCP server, you describe what you want in plain English and the AI handles the REST API calls, validates inputs, and warns you before anything destructive happens.

**What makes it different:**
- Every destructive operation requires explicit confirmation and shows you exactly what will happen
- Config backup before every delete/reboot — with a one-line rollback command (and an explicit warning if a backup point can't be captured)
- Rate limiting on every mutating tool prevents runaway AI loops from flooding your firewall
- Positive input validation (IP/port/MAC/CIDR) plus path-traversal/XSS screening, and secrets redacted from logs *and* API error responses
- Wire-format verified against the pfSense REST API v2.10.0 schema by a contract-test layer, so tools send exactly what the API expects

## Quick Start

**Prerequisites:** Python 3.11+, pfSense with [REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) installed

**Option A — run without cloning (uvx):**

```bash
uvx --from git+https://github.com/gensecaihq/pfsense-mcp-server pfsense-mcp-server
```

**Option B — clone for development:**

```bash
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set PFSENSE_URL, AUTH_METHOD, and credentials
```

**Connect to Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`.

Using the installed entry point (Option A):

```json
{
  "mcpServers": {
    "pfsense": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/gensecaihq/pfsense-mcp-server", "pfsense-mcp-server"],
      "env": {
        "PFSENSE_URL": "https://192.168.1.1",
        "AUTH_METHOD": "basic",
        "PFSENSE_USERNAME": "admin",
        "PFSENSE_PASSWORD": "your-password",
        "PFSENSE_VERSION": "CE_2_8_1",
        "VERIFY_SSL": "false"
      }
    }
  }
}
```

Or running from a clone (Option B):

```json
{
  "mcpServers": {
    "pfsense": {
      "command": "python3.11",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/pfsense-mcp-server",
      "env": {
        "PFSENSE_URL": "https://192.168.1.1",
        "AUTH_METHOD": "basic",
        "PFSENSE_USERNAME": "admin",
        "PFSENSE_PASSWORD": "your-password",
        "PFSENSE_VERSION": "CE_2_8_1",
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

333 tools across every major pfSense subsystem:

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
| **System** | 44 | Status, settings, diagnostics, state table, config history, reboot, ping. |
| **Services** | 14 | Start/stop/restart services. NTP, cron, SSH, service watchdog. |
| **Logs** | 3 | Firewall log analysis with parsed IPv4/IPv6 filterlog data. |
| **Traffic Shaping** | 12 | Shapers, queues, and limiters for bandwidth management. |
| **Schedules** | 8 | Time-based firewall rule scheduling. |
| **Virtual IPs** | 5 | CARP, ProxyARP, and IP Alias management. |
| **Troubleshooting** | 10 | Diagnose connectivity, blocked traffic, VPN, DHCP, DNS, HA. Full health report. |
| **Packages** | 49 | HAProxy, ACME/Let's Encrypt, BIND DNS, FreeRADIUS. |
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

Every one of the 202 mutating tools carries a guardrail, enforced at registration by a meta-test so a new tool can't ship ungated: the 52 destructive (delete/reboot/halt) tools require `confirm=True`, and the other 150 (create/update/apply/manage/export/service-control) are rate-limited, audited, and allowlist-checked. Sensitive parameters (passwords, keys, PSKs, bind passwords, tokens) are redacted in the audit log **and** in echoed API error responses.

You can also:
- Pass `dry_run=True` to preview any destructive operation without executing
- Pass `verify_descr="Allow HTTPS"` to verify you're deleting the right rule (guards against ID shifts)
- Set `MCP_READ_ONLY=true` to expose only the 131 read-only tools (search, get, diagnose)
- Set `MCP_ALLOWED_TOOLS=search_firewall_rules,get_firewall_log` to restrict to specific tools

See [SECURITY.md](SECURITY.md) for the vulnerability-disclosure policy and deployment-hardening guidance.

## Supported pfSense Versions

| Version | REST API package | Status |
|---|---|---|
| pfSense CE 2.8.1 | [v2.10.0](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.0) (latest) | Verified |
| pfSense Plus 26.03.1 | [v2.10.0](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.0) (latest) | Supported |
| pfSense Plus 26.03 | [v2.10.0](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.0) (latest) | Verified |
| pfSense Plus 25.11.1 | [v2.10.0](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.0) (latest) | Supported |
| pfSense Plus 25.11 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.7.3) (legacy) | Verified |
| pfSense CE 2.8.0 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.7.3) (legacy) | Supported |
| pfSense Plus 24.11 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.7.3) (legacy) | Supported |

Requires the [pfSense REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) by [jaredhendrickson13](https://github.com/jaredhendrickson13). Package v2.8.x+ ships builds only for CE 2.8.1 and Plus 25.11.1/26.03/26.03.1; v2.7.3 is the last release with builds for CE 2.8.0 and Plus 24.11/25.11.

> **Security note:** run REST API package **v2.10.0+**. It fixes a command-injection
> flaw in the interface-group endpoints
> ([GHSA-w3w4-mvcc-vmgr](https://github.com/pfrest/pfSense-pkg-RESTAPI/security/advisories/GHSA-w3w4-mvcc-vmgr))
> and adds core command auto-escaping; v2.9.0 fixed an earlier settings-sync
> privilege escalation ([GHSA-8q8g-9f77-8g8g](https://github.com/pfrest/pfSense-pkg-RESTAPI/security/advisories/GHSA-8q8g-9f77-8g8g)).
>
> v2.10.0 also marks `OpenVPNClient.auth_pass`, `User.ipsecpsk`, and
> `WireGuardPeer.presharedkey` as **sensitive**, so the API no longer returns
> them by default. This server still *sets* them normally; if a workflow needs
> to read one back, add a sensitive-field override in the REST API settings.

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
python3 -m src.main          # from a clone
pfsense-mcp-server           # via the installed console entry point (pip/uvx/pipx)
```

**HTTP** — for remote access and multi-client setups:
```bash
python3 -m src.main -t streamable-http --port 3000
```

**Docker** — hardened container with read-only filesystem:
```bash
docker compose up
```

Container security: non-root user (`mcp:1000`), read-only filesystem, all capabilities dropped, `noexec` tmpfs, `no-new-privileges`. In HTTP mode the container health check probes an unauthenticated `/health` endpoint (the `/mcp` endpoint requires a bearer token).

## Configuration

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `PFSENSE_URL` | Yes | — | pfSense URL (e.g., `https://192.168.1.1`) |
| `AUTH_METHOD` | | `api_key` | `api_key`, `basic`, or `jwt` |
| `PFSENSE_API_KEY` | * | — | REST API key |
| `PFSENSE_USERNAME` | * | — | pfSense username (for basic/jwt) |
| `PFSENSE_PASSWORD` | * | — | pfSense password (for basic/jwt) |
| `PFSENSE_VERSION` | | `CE_2_8_1` | Current: `CE_2_8_1`, `PLUS_25_11_1`, `PLUS_26_03`, `PLUS_26_03_1`. Legacy (still accepted): `CE_2_8_0`, `PLUS_24_11`, `PLUS_25_11`, `CE_26_03` |
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
python3 -m pytest tests/ -v          # 481 tests
python3 -m pytest tests/ --cov=src   # with coverage (~46%)
```

The suite includes a **wire-contract layer** (`tests/contract/`) that asserts every tool's payload against the real pfSense REST API v2.10.0 schema (distilled from the upstream OpenAPI spec), so a wrong field name or type is a failing test rather than a silent misconfiguration. CI runs on Python 3.11/3.12/3.13 with `pip-audit` dependency scanning.

On top of the in-process suite, an **end-to-end protocol smoke test** drives the
server over the real MCP wire protocol with the official
[MCP Inspector](https://github.com/modelcontextprotocol/inspector) CLI — on
both transports, in CI on every push:

```bash
make test-e2e            # or: ./scripts/inspector_smoke.sh  (needs node/npx, jq)
```

It verifies the initialize handshake, the 333-tool listing with annotations,
the guardrail confirm-gate over the wire, read-only mode, and HTTP bearer-auth
plus Origin enforcement — no pfSense instance required.

## MCP Specification Compliance

Compliant with [MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) — the newest revision with stable SDK support — and negotiates down to older revisions per connection, so existing clients keep working:

- `ToolAnnotations` on all 333 tools (readOnlyHint, destructiveHint, idempotentHint)
- `serverInfo.version` and `instructions` provided
- Origin header validation (MUST requirement)
- Bearer token auth with timing-safe comparison
- Default bind to localhost per spec SHOULD
- stdio and Streamable HTTP transports

The newest revision, [MCP 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/changelog), makes the protocol stateless; SDK support ships in fastmcp 4, currently in beta. This codebase already passes its full test suite on the fastmcp 4 beta (checked continuously by a non-blocking CI job), and uses none of the features 2026-07-28 deprecates (Roots, Sampling, MCP Logging), so adopting the sessionless protocol when fastmcp 4 is stable is a dependency-pin change. fastmcp 4 servers negotiate the protocol era per connection, keeping today's handshake-era clients fully supported.

## Project Structure

```
src/
  main.py              Entry point (transports, read-only filter, key validation)
  server.py            FastMCP instance + API client
  client.py            pfSense REST API v2 HTTP client (retry/backoff, pooling)
  guardrails.py        Risk classification, confirm gate, rate limit, audit, redaction
  helpers.py           Validation, parsing, pagination, safety guards
  models.py            Data models
  middleware.py        HTTP bearer auth + Origin validation + /health
  tools/               34 tool modules (333 tools)
scripts/
  generate_contract.py Regenerate the wire contract from an OpenAPI spec
  generate_token.py    Generate a secure MCP_API_KEY bearer token
  inspector_smoke.sh   End-to-end MCP protocol smoke test (MCP Inspector CLI)
tests/                 481 tests (incl. tests/contract/ wire-contract suite)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the request lifecycle, guardrail
model, and wire-contract layer; [SECURITY.md](SECURITY.md) for disclosure and
hardening; and [RELEASE_AUDIT.md](RELEASE_AUDIT.md) for the audit and roadmap.

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
- [JeremiahChurch](https://github.com/JeremiahChurch) — modular rewrite (PR #5), log endpoint OOM safeguards (PR #6)
- [shawnpetersen](https://github.com/shawnpetersen) — API v2 endpoint discovery (PR #3)
- [aemitic](https://github.com/aemitic) — DELETE-body fix (PR #9), firewall `ipprotocol` for IPv6/dual-stack (PR #10), `logconfigchanges` (PR #11)
- [hossamnagy](https://github.com/hossamnagy) — resilient startup on transient preflight failure (PR #14)
- [bill-mccormick-dg](https://github.com/bill-mccormick-dg) — independent DELETE-body fix (PR #16)
- [w1ld3r](https://github.com/w1ld3r) — DELETE and remote-syslog bug reports (#12, #13)
- tvlc — WebGUI port type-mismatch report (#7)
- [renanwilliam](https://github.com/renanwilliam) — uvx/pipx packaging request (#8)
- [Netgate](https://netgate.com) — pfSense
- [FastMCP](https://gofastmcp.com) — MCP framework
