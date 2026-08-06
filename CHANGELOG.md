# Changelog

All notable changes to the pfSense MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Post-1.0.0 bug fixes and quality improvements, all merged to `main`. No tool
count change (still 327); test suite grew from 308 to 337.

### Fixed

- **`remove_from_alias` failed on aliases with per-entry descriptions** (400 `TOO_MANY_ALIAS_DETAILS`). The API's remove control flag strips only `address` entries, leaving the parallel `detail` list longer than the address list, which the API then rejects. `manage_alias_addresses(action="remove")` now reads the alias and rebuilds both lists in lockstep before PATCHing.
- **`create_firewall_schedule` could not actually create a schedule.** The pfSense API requires at least one time range at creation ("Field `timerange` is required"), but the tool never sent one. It now takes `hour`/`position`/`month`/`day`/`rangedescr` for the initial time range (further ranges via `create_schedule_time_range`) and validates that either `position` (weekdays) or `month`+`day` is provided. Also corrected `month`/`day`/`position` on `create_schedule_time_range`/`update_schedule_time_range` from `str` to `List[int]` to match the API schema, with docstrings explaining pfSense's semantics (`position` = weekday numbers 1–7). Verified end-to-end against a live pfSense 26.03 instance.
- **All `delete_*` tools were non-functional** (#12, PR #9, PR #16). `httpx.AsyncClient.delete()` does not accept a `json=` kwarg, so every delete (firewall rules, NAT, aliases, DHCP mappings, etc.) raised `TypeError` before any HTTP traffic. DELETE now routes through `client.request("DELETE", ...)`, which supports the JSON body pfSense requires.
- **`update_log_settings` could not enable remote syslog and silently dropped fields** (#13, PR #11). The wire-format keys `ipproto` and `reverse` were ignored by the API; renamed to `ipprotocol` and `reverseorder`. Added `enableremotelogging` (the master toggle), `logconfigchanges`, and the per-category remote-syslog toggles (`auth`, `portalauth`, `vpn`, `dpinger`, `hostapd`, `system`, `resolver`, `ppp`, `routing`, `ntpd`).
- **`update_webgui_settings` could not change the WebGUI port** (#7). The pfSense REST API requires `port` as a string; the tool now accepts an `int` for ergonomics and coerces it to a string before sending.
- **Log endpoints could hang until pfSense ran out of memory** (PR #6). Added a 10-second read-phase timeout and classification of read-phase failures (`ReadError`/`RemoteProtocolError`/`ReadTimeout`) into a clear, actionable message (upstream tracking: pfSense-pkg-RESTAPI#806), with docstring warnings on the log tools.
- **Transient connectivity blip at launch killed the server** (PR #14). A momentary preflight failure before the stdio channel opens now logs a warning and starts anyway; individual tools surface connectivity errors when invoked.

### Added

- **Schedule-based firewall rules.** The schedule tools (`create_firewall_schedule`, `create_schedule_time_range`, etc.) could build schedules, but no rule tool could reference one, so schedules were inert. `create_firewall_rule_advanced` and `update_firewall_rule` now expose a `schedule` parameter (sent as the API's `sched` field) to assign an existing schedule to a rule; on update, passing `""` detaches the schedule.
- **IPv6 / dual-stack firewall rules** (PR #10). `create_firewall_rule_advanced` exposes an `ipprotocol` parameter (`inet`, `inet6`, `inet46`) with validation instead of hardcoding `inet`.
- **uvx / pipx installation** (#8). Added a `pfsense-mcp-server` console entry point and setuptools package discovery, so the server can run without cloning the repository.

### Changed

- **pfSense version matrix refreshed for the current stable releases.** `PFSENSE_VERSION` now accepts `PLUS_26_03_1` (pfSense Plus 26.03.1), `PLUS_26_03`, and `PLUS_25_11_1` alongside `CE_2_8_1`; all previous values (`CE_2_8_0`, `PLUS_24_11`, `PLUS_25_11`, and the historically mislabeled `CE_26_03`, now an alias of `PLUS_26_03`) keep working. The default is now `CE_2_8_1` (current CE stable). Docs updated for REST API package v2.9.0 — the latest release, which ships builds for CE 2.8.1 and Plus 25.11.1/26.03/26.03.1 and fixes [GHSA-8q8g-9f77-8g8g](https://github.com/pfrest/pfSense-pkg-RESTAPI/security/advisories/GHSA-8q8g-9f77-8g8g) — with v2.7.3 documented as the legacy path for CE 2.8.0 and Plus 24.11/25.11. This server calls neither the settings-sync endpoint nor the new hasync endpoint, so v2.9.0's breaking changes do not affect it.
- **FastMCP upgraded from 2.14.0 to 3.4.6** (`fastmcp>=3.4.6,<4.0`). fastmcp 3 declares its dependencies correctly, so the 2.14.0-era workaround pins for `pydantic-settings` and `mcp` are replaced by a single explicit `mcp>=1.24.0,<2.0.0` (a direct dependency: the tool modules import `mcp.types.ToolAnnotations`). Server behavior is unchanged — same 327 tools, stdio + Streamable HTTP transports, bearer auth, and MCP 2025-11-25 with per-connection negotiation down to older revisions — verified end-to-end (in-memory MCP client: initialize, tools/list, tools/call; HTTP: 401 without token, 403 on bad Origin, protocol negotiation at 2025-06-18 and 2025-11-25). In fastmcp 3, `@mcp.tool` returns the plain function instead of a `FunctionTool` wrapper, so the test suite's `.fn` unwrapping was dropped; `test_enhanced_connection` (a tool whose name matches pytest's collection pattern) is now marked `__test__ = False` so pytest cannot execute the real connection tool as a test.
- **Forward-compat CI probe for MCP spec 2026-07-28.** A non-blocking CI job runs the full suite against fastmcp 4.0.0b1 (mcp SDK 2.x, sessionless protocol). The suite passes unmodified, so adopting the stateless protocol when fastmcp 4 leaves beta is a pin change; fastmcp 4 negotiates the protocol era per connection, preserving backward compatibility with handshake-era clients.
- CI is green. The `ruff check src/ tests/` step had been failing on 80 pre-existing lint issues since before the 1.0.0 tag; all are resolved with no behavior change.

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
