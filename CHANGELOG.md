# Changelog

All notable changes to the pfSense MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-26

### First Stable Release

Production-ready MCP server for pfSense firewall management with 327 tools, 9-layer defense-in-depth guardrail system, and full MCP spec 2025-11-25 compliance. Verified against the pfSense REST API v2 PHP source code and validated with 568 end-to-end checks across 8 audit phases with 0 failures.

### Tools (327 total across 34 files)

- **Firewall** (43 tools) — Rules, aliases, schedules, states, virtual IPs, traffic shaping
- **NAT** (16 tools) — Port forwards, outbound NAT, 1:1 NAT
- **VPN** (51 tools) — OpenVPN, IPsec, WireGuard with full CRUD, encryption, apply, status
- **Routing** (16 tools) — Gateways, gateway groups, static routes, default gateway, apply
- **DNS** (24 tools) — DNS Resolver (Unbound) and DNS Forwarder (dnsmasq)
- **DHCP** (17 tools) — Leases, static mappings, address pools, custom options, server config
- **Certificates** (15 tools) — Certs, CAs, CRLs with generate, renew, PKCS12 export
- **Users** (12 tools) — Users, groups, auth servers
- **Interfaces** (14 tools) — Config, VLANs, bridges, groups, apply
- **System & Diagnostics** (44 tools) — Status, settings, ping, reboot, config history/restore
- **Services** (14 tools) — Core services, NTP, cron, service watchdog, SSH, Wake-on-LAN
- **Logs** (3 tools) — Firewall logs with parsed filterlog CSV (IPv4/IPv6)
- **Packages** (43 tools) — HAProxy, ACME/Let's Encrypt, BIND DNS, FreeRADIUS
- **Troubleshooting** (10 tools) — RCA diagnostics, health report, audit trail
- **Utility** (9 tools) — HATEOAS, object IDs, guardrail status, risk check

### Security — 9-Layer Defense-in-Depth

1. **Action Classification** — 5 risk levels (read/low/medium/high/critical) auto-assigned to every tool
2. **Mandatory Approval Gate** — All 52 destructive tools require `confirm=True` with full impact visualization
3. **Input Sanitization** — Recursive detection of command injection, directory traversal, XSS across all parameters
4. **Rate Limiting** — Sliding-window throttle: 20 creates/60s, 10 deletes/60s, 2 critical/300s
5. **Audit Logging** — JSON lines format with redacted parameters, pre and post execution
6. **Dry-Run Mode** — Preview any destructive operation without executing
7. **Sensitive Data Redaction** — 15 key patterns (passwords, tokens, certs) auto-redacted in all outputs
8. **Command Allowlisting** — Optional `MCP_ALLOWED_TOOLS` restriction
9. **Automatic Config Backup** — Pre-change config revision captured before every destructive operation with rollback instructions

### MCP Compliance

- MCP specification 2025-11-25 (latest)
- `serverInfo.version` and `instructions` provided
- `ToolAnnotations` on all 327 tools (readOnlyHint, destructiveHint, idempotentHint)
- Origin header validation per spec MUST requirement
- Bearer token auth with timing-safe comparison
- Default bind to 127.0.0.1 per spec SHOULD
- Read-only mode (`MCP_READ_ONLY=true`) for least-privilege deployments

### Deployment

- **Transports**: stdio (Claude Desktop/Code) and Streamable HTTP (remote)
- **Docker**: Multi-stage build, non-root user, read-only filesystem, dropped capabilities, noexec tmpfs
- **Authentication**: API Key, Basic Auth, JWT (all three pfSense REST API v2 methods)
- **Configuration**: 21 environment variables, all documented with safe defaults

### Testing

- 308 unit tests passing
- 568 end-to-end validation checks across 8 audit phases
- 0 failures in structural integrity, API contract, guardrail enforcement, rate limiting, injection attacks, real-world workflows, crash scenarios

### pfSense Compatibility

| pfSense Version | REST API Package | Status |
|---|---|---|
| pfSense CE 2.8.1 | v2.7.3 | Verified |
| pfSense Plus 25.11 | v2.7.3 | Verified |
| pfSense CE 2.8.0 | v2.6.0+ | Supported |
| pfSense Plus 24.11 | v2.6.0+ | Supported |
