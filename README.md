<div align="center">

# 🛡️ pfSense MCP Server

### Manage your pfSense firewall in plain English — from Claude Desktop, Claude Code, or any MCP client.

**332 tools** across every subsystem · **wire-format verified** against the pfSense REST API · **safety guardrails** on every change

<br>

[![Release](https://img.shields.io/github/v/release/gensecaihq/pfsense-mcp-server?label=release)](https://github.com/gensecaihq/pfsense-mcp-server/releases/latest)
[![CI](https://github.com/gensecaihq/pfsense-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/gensecaihq/pfsense-mcp-server/actions/workflows/ci.yml)
[![MCP 2025-11-25](https://img.shields.io/badge/MCP-2025--11--25-6E56CF.svg)](https://modelcontextprotocol.io)
[![pfSense API v2.10.2](https://img.shields.io/badge/pfSense%20API-v2.10.2-orange.svg)](https://pfrest.org/)
[![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%20|%203.12%20|%203.13-3776AB.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-661%20passing-brightgreen.svg)](#testing)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

</div>

---

```text
You:     Block all traffic from 203.0.113.5 on WAN
Claude:  ✓ created block rule  →  ✓ applied changes  →  rollback point: config revision 42

You:     Why can't 192.168.1.50 reach the internet?
Claude:  ran diagnostics → gateway WAN_DHCP is down, and a block rule on LAN matches this host

You:     Add a WireGuard peer for my laptop and show me the config
Claude:  ✓ created peer on tun_wg0  →  here's the client config to import
```

**pfSense MCP Server** connects [Claude Desktop](https://claude.ai/download), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), and any other [MCP](https://modelcontextprotocol.io) client to your pfSense firewall. Ask questions, diagnose issues, and change configuration through conversation. Every destructive action needs explicit confirmation, and the server records the config revision it can be rolled back to.

Letting an AI change a production firewall is only safe if the details are right, and that's where the work went:
- A contract-test layer checks every tool's request format against the pfSense REST API schema.
- Every change goes through a multi-layer guardrail pipeline.
- CI runs 661 tests on Python 3.11–3.13, plus an end-to-end MCP protocol test.

**Latest release: [v1.1.0](https://github.com/gensecaihq/pfsense-mcp-server/releases/tag/v1.1.0)** · [Changelog](CHANGELOG.md)

> [!TIP]
> Jump to the [Quick Start](#quick-start). Setup takes about two minutes with `uvx`, and you don't need to clone anything. If this project is useful to you, a ⭐ helps others find it.

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
[Known limitations](#known-limitations) ·
[Architecture](ARCHITECTURE.md) ·
[Contributing](CONTRIBUTING.md)

## Why This Exists

Managing a pfSense firewall means clicking through web UI tabs, remembering field names, and hoping you don't fat-finger a rule that locks you out. With this MCP server, you describe what you want in plain English and the AI handles the REST API calls, validates inputs, and warns you before anything destructive happens.

**What makes it different:**
- Every destructive operation requires explicit confirmation and shows you exactly what will happen
- The config revision is captured before every high-risk change. The response gives the revision ID to restore from **Diagnostics › Backup & Restore › Config History** in the webGUI, or warns explicitly if no revision could be captured.
- Rate limits on every tool that changes configuration stop a runaway AI loop from flooding your firewall
- Positive input validation (IP/port/MAC/CIDR) plus path-traversal/XSS screening, and secrets redacted from logs *and* API error responses
- Wire-format verified against the pfSense REST API v2.10.2 schema by a contract-test layer, so tools send exactly what the API expects

## Quick Start

**Prerequisites:**
- Python 3.11 or later.
- pfSense with the [REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) installed. See [Supported pfSense versions](#supported-pfsense-versions).
- For Option A, [uv](https://docs.astral.sh/uv/).

> [!IMPORTANT]
> This project is **not published on PyPI**. A different, unrelated project uses the PyPI name `pfsense-mcp-server`, so never run `pip install pfsense-mcp-server`. Install from Git or from the [release assets](https://github.com/gensecaihq/pfsense-mcp-server/releases/latest) as shown below.

**Option A: run without cloning (uvx):**

```bash
uvx --from git+https://github.com/gensecaihq/pfsense-mcp-server@v1.1.0 pfsense-mcp-server
```

**Option B: clone for development:**

```bash
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set PFSENSE_URL, AUTH_METHOD, and credentials
```

**Connect to Claude Desktop.** Add the server to `claude_desktop_config.json`:
- macOS: `~/Library/Application Support/Claude/`
- Windows: `%APPDATA%\Claude\`

Using the installed entry point (Option A):

```json
{
  "mcpServers": {
    "pfsense": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/gensecaihq/pfsense-mcp-server@v1.1.0", "pfsense-mcp-server"],
      "env": {
        "PFSENSE_URL": "https://192.168.1.1",
        "AUTH_METHOD": "basic",
        "PFSENSE_USERNAME": "admin",
        "PFSENSE_PASSWORD": "your-password",
        "PFSENSE_VERSION": "CE_2_8_1",
        "PFSENSE_CA_FILE": "/path/to/pfsense-ca.pem"
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
      "command": "python3",
      "args": ["-m", "src.main"],
      "cwd": "/path/to/pfsense-mcp-server",
      "env": {
        "PFSENSE_URL": "https://192.168.1.1",
        "AUTH_METHOD": "basic",
        "PFSENSE_USERNAME": "admin",
        "PFSENSE_PASSWORD": "your-password",
        "PFSENSE_VERSION": "CE_2_8_1",
        "PFSENSE_CA_FILE": "/path/to/pfsense-ca.pem"
      }
    }
  }
}
```

Remove `PFSENSE_CA_FILE` if your pfSense certificate is signed by a public CA.

**About the CA file.** pfSense ships with a self-signed certificate from its own
CA, and Python does not read your OS trust store, so verification fails out of
the box. Export the CA at **System > Cert. Manager > CAs** (the export-certificate
icon), save the PEM anywhere readable, and point `PFSENSE_CA_FILE` at it. A
missing or unparseable file is a startup error, never a silent downgrade.

`VERIFY_SSL=false` also connects, and is fine for a throwaway lab. Understand what
it costs: nothing authenticates the firewall, so anything that can intercept the
connection can read the API key and act as the firewall. This tool changes
firewall rules — treat that credential accordingly.

**Start talking to your firewall.** Open Claude Desktop and ask:
- *"Show me all blocked traffic in the last hour"*
- *"What services are running?"*
- *"Create a port forward for port 443 to 192.168.1.50"*
- *"Run a full system health check"*

## What You Can Do

332 tools across every major pfSense subsystem:

| Domain | Tools | What You Can Do |
|---|:---:|---|
| **Firewall Rules** | 9 | Create, update, delete, reorder rules. Bulk block IPs. View compiled pf ruleset. |
| **Aliases** | 5 | Manage host/network/port/URL aliases. Add and remove addresses. |
| **NAT** | 16 | Port forwards, outbound NAT, 1:1 NAT — full lifecycle management. |
| **VPN** | 51 | OpenVPN servers and clients, IPsec tunnels, WireGuard peers — CRUD, status, apply. |
| **Routing** | 16 | Gateways, gateway groups, static routes, default gateway management. |
| **DNS** | 23 | Unbound resolver and dnsmasq forwarder: host overrides, domain overrides, access lists. |
| **DHCP** | 17 | Leases, static mappings, address pools, custom options, server config. |
| **Certificates** | 15 | Certs, CAs, CRLs — generate, renew, export PKCS12. |
| **Users** | 12 | User accounts, groups, LDAP/RADIUS auth server config. |
| **Interfaces** | 14 | Interface config, VLANs, bridges, groups. |
| **System** | 43 | Status, settings, diagnostics, state table, config history, reboot, ping. |
| **Services** | 14 | Start/stop/restart services. NTP, cron, SSH, service watchdog. |
| **Logs** | 4 | Firewall log analysis with parsed IPv4/IPv6 filterlog data. Raw tail/grep reads of the dhcpd/filter/resolver/system/auth log files. |
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
    "rollback_instruction": "To undo this change, restore revision 42 manually in the pfSense webGUI: Diagnostics > Backup & Restore > Config History."
  }
```

All 201 tools that change configuration carry a guardrail, and a test fails the build if a new one ships without it.
- **Every change tool** is rate-limited, audit-logged and checked against the allowlist.
- **High-risk tools (51):** deletes, disconnects, reboot, halt and bulk block are also blocked until the caller passes `confirm=True`.
- **`manage_*` tools:** these require `confirm=True` for their remove and delete actions.
- **Secrets:** passwords, keys, PSKs, bind passwords and tokens are redacted in the audit log **and** in echoed API error responses.

`confirm=True` is a parameter the MCP client sends. It is not a separate human-approval step, so keep your client's tool-approval prompts on for destructive tools.

You can also:
- Pass `dry_run=True` to preview any destructive operation without running it.
- Pass `verify_descr="Allow HTTPS"` to check that you're changing or deleting the rule you expect. This guards against rule IDs shifting.
- Set `MCP_READ_ONLY=true` to expose only the 131 read-only tools (search, get, diagnose).
- Set `MCP_ALLOWED_TOOLS=create_firewall_rule_advanced,delete_firewall_rule` to permit only the listed write tools. Read tools stay available.

See [SECURITY.md](SECURITY.md) for the vulnerability-disclosure policy and deployment-hardening guidance.

## Supported pfSense Versions

| Version | REST API package | Status |
|---|---|---|
| pfSense CE 2.9.0 | [v2.10.2](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.2) (latest) | Supported |
| pfSense CE 2.8.1 | [v2.10.2](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.2) (latest) | Verified |
| pfSense Plus 26.07 | [v2.10.2](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.2) (latest) | Supported |
| pfSense Plus 26.03.1 | [v2.10.2](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.2) (latest) | Supported |
| pfSense Plus 26.03 | [v2.10.2](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.2) (latest) | Verified |
| pfSense Plus 25.11.1 | [v2.10.2](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.10.2) (latest) | Supported |
| pfSense Plus 25.11 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.7.3) (legacy) | Verified |
| pfSense CE 2.8.0 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.7.3) (legacy) | Supported |
| pfSense Plus 24.11 | [v2.7.3](https://github.com/pfrest/pfSense-pkg-RESTAPI/releases/tag/v2.7.3) (legacy) | Supported |

Requires the [pfSense REST API v2 package](https://github.com/pfrest/pfSense-pkg-RESTAPI) by [jaredhendrickson13](https://github.com/jaredhendrickson13). Package v2.8.x+ ships builds only for CE 2.8.1 and Plus 25.11.1/26.03/26.03.1; CE 2.9.0 and Plus 26.07 need v2.10.1+; v2.7.3 is the last release with builds for CE 2.8.0 and Plus 24.11/25.11.

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
| **JWT** | `AUTH_METHOD=jwt` + username/password | Short-lived tokens, obtained and renewed automatically (assumes pfSense's default 1-hour lifetime) |

## Deployment Options

**stdio** (default) — for Claude Desktop and Claude Code:
```bash
python3 -m src.main          # from a clone
pfsense-mcp-server           # via the installed console entry point (pip/uvx/pipx)
```

**HTTP**: for remote access and multi-client setups. It requires `MCP_API_KEY`, and the server refuses to start with an empty, placeholder or short token.
```bash
export MCP_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python3 -m src.main -t streamable-http --port 3000
```
The HTTP transport is plain HTTP. Put it behind a TLS-terminating reverse proxy before exposing it beyond localhost.

**Docker**: a hardened container running the HTTP transport.
```bash
cp .env.example .env        # set PFSENSE_URL, credentials, and MCP_API_KEY
docker compose up -d
```

The published port binds to `127.0.0.1` by default. Set `MCP_BIND_ADDR=0.0.0.0` to expose it, but only behind TLS. For a private CA, put the PEM in `./certs/` and set `PFSENSE_CA_FILE=/certs/<file>.pem`.

Container security:
- Runs as a non-root user (`mcp:1000`).
- Read-only filesystem, a `noexec` tmpfs, and `no-new-privileges`.
- All Linux capabilities dropped.

The health check probes an unauthenticated `/health` endpoint, because `/mcp` requires the bearer token.

**Behind an MCP gateway** — the HTTP transport is a spec-compliant Streamable
HTTP endpoint with bearer-token auth, so it can be registered as an MCP-server
target behind managed gateways such as
[AWS Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-MCPservers.html)
(use its API-key credential provider to supply the `MCP_API_KEY` bearer token,
and add the gateway's origin to `MCP_ALLOWED_ORIGINS`). Such gateways add
centralized OAuth/IAM in front and translate between protocol revisions,
including 2026-07-28. No gateway is required — this is purely an option for
environments that already run one.

## Configuration

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `PFSENSE_URL` | Yes | — | pfSense URL (e.g., `https://192.168.1.1`) |
| `AUTH_METHOD` | | `api_key` | `api_key`, `basic`, or `jwt` |
| `PFSENSE_API_KEY` | * | — | REST API key |
| `PFSENSE_USERNAME` | * | — | pfSense username (for basic/jwt) |
| `PFSENSE_PASSWORD` | * | — | pfSense password (for basic/jwt) |
| `PFSENSE_VERSION` | | `CE_2_8_1` | Current: `CE_2_8_1`, `CE_2_9_0`, `PLUS_25_11_1`, `PLUS_26_03`, `PLUS_26_03_1`, `PLUS_26_07`. Legacy (still accepted): `CE_2_8_0`, `PLUS_24_11`, `PLUS_25_11`, `CE_26_03` |
| `VERIFY_SSL` | | `true` | `false` disables certificate checking entirely — prefer `PFSENSE_CA_FILE` |
| `PFSENSE_CA_FILE` | | — | PEM file for pfSense's private/self-signed CA, so verification stays on |
| `API_TIMEOUT` | | `30` | Request timeout in seconds |
| `MCP_READ_ONLY` | | `false` | Only expose read-only tools |
| `MCP_ENABLE_LOG_FILES` | | `true` | Set `false` to remove `get_log_file` (raw `/var/log/*` reads via command sink) |

Boolean settings accept `true/false`, `1/0`, `yes/no` or `on/off`. Any other value stops the server at startup rather than guessing, so a typo can't turn off TLS verification.

<details>
<summary>All configuration options</summary>

| Variable | Default | Description |
|---|---|---|
| `ENABLE_HATEOAS` | `false` | Enable HATEOAS links in API responses |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `MCP_HOST` | `127.0.0.1` | Bind address for HTTP mode |
| `MCP_PORT` | `3000` | Port for HTTP mode |
| `MCP_BIND_ADDR` | `127.0.0.1` | Docker Compose only: host address the published port binds to |
| `MCP_API_KEY` | — | Bearer token for HTTP transport (required) |
| `MCP_ALLOWED_ORIGINS` | localhost | Comma-separated allowed origins |
| `MCP_AUDIT_LOG` | — | Path to audit log file (JSON lines) |
| `MCP_RATE_LIMIT_DELETE` | `10` | Max deletes per 60 seconds |
| `MCP_RATE_LIMIT_CREATE` | `20` | Max creates per 60 seconds |
| `MCP_RATE_LIMIT_UPDATE` | `30` | Max settings changes (`update_*`, `apply_*`, `enable_*`/`disable_*`) per 60 seconds |
| `MCP_RATE_LIMIT_CRITICAL` | `2` | Max critical ops per 300 seconds |
| `MCP_ALLOWED_TOOLS` | all | Comma-separated allowlist of write tools. Read tools are always available; `get_log_file` is controlled by `MCP_ENABLE_LOG_FILES` |
| `MCP_ROLLBACK_BUFFER` | `50` | Rollback entries kept in memory |
| `RESPONSE_FORMAT` | `json` | `gcf` re-encodes tool results as [Graph Compact Format](https://gcformat.com) for fewer tokens (requires the `gcf` extra) |

</details>

### Response Encoding (GCF)

By default the tools return JSON. Setting `RESPONSE_FORMAT=gcf` returns each eligible tool result as a single [Graph Compact Format](https://gcformat.com) block instead: the record arrays these read tools produce (firewall rules, aliases, DHCP leases, certificates, DNS records) have their repeated field names factored into one header, cutting the token cost when the result crosses the LLM boundary. Results that are not a single JSON body — or that GCF would not shrink — stay JSON (see below).

Install the optional extra into the server's environment and set the variable:

```bash
pip install '.[gcf]'        # from a clone of this repo
export RESPONSE_FORMAT=gcf

# or, with uvx (the extra must go into uvx's isolated tool environment):
RESPONSE_FORMAT=gcf uvx --with 'gcf-python[fastmcp]==2.7.1' \
  --from git+https://github.com/gensecaihq/pfsense-mcp-server pfsense-mcp-server
```

It is opt-in and conservative — GCF is used only when it is both smaller than the JSON and a verified lossless round-trip, otherwise the JSON is kept, so no record is ever dropped or altered. `structuredContent` is preserved, so output-schema validation and non-model clients keep receiving JSON. If the `gcf` extra is not installed, the server logs a warning and continues with JSON.

Token savings on representative 30-record results (o200k tokens, lossless; reproduce with `python benchmarks/gcf_benchmark.py`):

| Result | JSON | GCF | Savings |
|---|---:|---:|---:|
| Firewall rules | 1,995 | 936 | **53.1%** |
| Aliases | 1,065 | 594 | **44.2%** |
| DHCP leases | 2,314 | 1,606 | **30.6%** |

## Testing

```bash
python3 -m pytest tests/ -v          # 661 tests
python3 -m pytest tests/ --cov=src   # with coverage (~50%)
```

The suite includes a **wire-contract layer** (`tests/contract/`) that asserts every tool's payload against the real pfSense REST API v2.10.2 schema (distilled from the upstream OpenAPI spec), so a wrong field name or type is a failing test rather than a silent misconfiguration. CI runs on Python 3.11/3.12/3.13 with `pip-audit` dependency scanning.

In addition to the in-process suite, an **end-to-end protocol smoke test** drives
the server over the real MCP wire protocol using the official
[MCP Inspector](https://github.com/modelcontextprotocol/inspector) CLI. It covers
both transports and runs in CI on every push:

```bash
make test-e2e            # or: ./scripts/inspector_smoke.sh  (needs node/npx, jq)
```

It verifies the initialize handshake, the 332-tool listing with annotations,
the guardrail confirm-gate over the wire, read-only mode, and HTTP bearer-auth
plus Origin enforcement — no pfSense instance required.

## MCP Specification Compliance

Compliant with [MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) — the newest revision with stable SDK support — and negotiates down to older revisions per connection, so existing clients keep working:

- `ToolAnnotations` on all 332 tools (readOnlyHint, destructiveHint, idempotentHint)
- `serverInfo.version` and `instructions` provided
- Origin header validation (MUST requirement)
- Bearer token auth with timing-safe comparison
- Default bind to localhost per spec SHOULD
- stdio and Streamable HTTP transports

### The stateless 2026-07-28 revision

[MCP 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/changelog) removes the `initialize` handshake and protocol-level sessions, so every request stands on its own. SDK support ships in fastmcp 4, which is now stable (4.0.5).

**Status:** this release pins fastmcp 3.x (MCP 2025-11-25). A non-blocking CI job runs the full test suite and the MCP Inspector smoke test against fastmcp 4.0.x, and both pass unchanged. The server holds no session state by design, and it uses none of the features that 2026-07-28 deprecates (Roots, Sampling, MCP Logging).

The pin will move to fastmcp 4 once the smoke test also covers sessionless requests, which skip `initialize`. fastmcp 4 negotiates the protocol version per connection, so clients that use the handshake will keep working.

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
  tools/               34 tool modules (332 tools)
scripts/
  generate_contract.py Regenerate the wire contract from an OpenAPI spec
  generate_token.py    Generate a secure MCP_API_KEY bearer token
  inspector_smoke.sh   End-to-end MCP protocol smoke test (MCP Inspector CLI)
tests/                 661 tests (incl. tests/contract/ wire-contract suite)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the request lifecycle, guardrail
model, and wire-contract layer; [SECURITY.md](SECURITY.md) for disclosure and
hardening; and [RELEASE_AUDIT.md](RELEASE_AUDIT.md) for the audit and roadmap.

## Known Limitations

These are tracked for the next release:

- About 11 update/delete tools for nested objects don't send the `parent_id` the REST API requires, so those calls fail ([#79](https://github.com/gensecaihq/pfsense-mcp-server/issues/79)). Affected objects are DHCP address pools and custom options, traffic-shaper queues, IPsec encryption entries and schedule time ranges.
- `create_ipsec_phase1` and `create_ipsec_phase2` don't yet send the nested encryption settings the API requires. Fixing them needs validation against a live pfSense.
- The REST API has no config-restore endpoint, so rolling back a change is a manual step in the webGUI. Use the revision ID that guarded tools return.
- Each server process manages a single pfSense instance.

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
- [JeremiahChurch](https://github.com/JeremiahChurch) — modular rewrite (PR #5), log endpoint OOM safeguards (PR #6), DHCP static-mapping search fix (PR #91)
- [shawnpetersen](https://github.com/shawnpetersen) — API v2 endpoint discovery (PR #3)
- [aemitic](https://github.com/aemitic) — DELETE-body fix (PR #9), firewall `ipprotocol` for IPv6/dual-stack (PR #10), `logconfigchanges` (PR #11)
- [pbhorjee](https://github.com/pbhorjee) — live-status diagnostics fix (PR #21), firewall-log freshness + exact-IP filtering (PR #23), redirect credential guard (PR #72), 503 write-retry fix (PR #74), transport-error context (PR #75), alias edit locking (PR #76), retry jitter and budget (PR #77), private-CA report (#73)
- [DrewKolstad](https://github.com/DrewKolstad) — interface addressing, null-safe search filters, WireGuard allowed IPs, DHCP lease times (PR #78)
- [msarg44](https://github.com/msarg44) — `get_pf_table` / `get_config_revision` fix (PR #80)
- [cbrown350](https://github.com/cbrown350) — `get_log_file` raw log reads (PR #90)
- [blackwell-systems](https://github.com/blackwell-systems) — optional GCF response encoding (PR #87)
- [bholland-bh](https://github.com/bholland-bh) — pfSense CE 2.9.0 / Plus 26.07 support request (#88)
- [hossamnagy](https://github.com/hossamnagy) — resilient startup on transient preflight failure (PR #14)
- [bill-mccormick-dg](https://github.com/bill-mccormick-dg) — independent DELETE-body fix (PR #16)
- [w1ld3r](https://github.com/w1ld3r) — DELETE and remote-syslog bug reports (#12, #13)
- tvlc — WebGUI port type-mismatch report (#7)
- [renanwilliam](https://github.com/renanwilliam) — uvx/pipx packaging request (#8)
- [Netgate](https://netgate.com) — pfSense
- [FastMCP](https://gofastmcp.com) — MCP framework
