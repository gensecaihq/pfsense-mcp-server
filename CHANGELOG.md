# Changelog

All notable changes to the pfSense MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Post-1.0.0 bug fixes and quality improvements, all merged to `main`. Tool count
grew from 327 to 333 (new ACME/HAProxy sub-resource tools); test suite grew from
308 to 475.

### Added

- **`SECURITY.md`** — private vulnerability-disclosure policy and deployment-hardening guidance for a firewall-management tool.
- **Wire-contract test layer.** `scripts/generate_contract.py` distills the
  upstream pfSense REST API OpenAPI spec (a pkg-RESTAPI release asset) into a
  slim, vendored contract (`tests/contract/contract-v2.9.0.json`) of every
  writable endpoint's valid fields, JSON types, enum choices, and
  create-required fields. `tests/contract/schema.py` asserts a tool's actual
  wire payload against it. This catches the class of bug where pfSense silently
  drops an unknown field (PATCH) or 400s on a mistyped/missing one (POST) —
  failures invisible to a mocked unit test. Regenerate with
  `python scripts/generate_contract.py <openapi.json> tests/contract/contract-<ver>.json --version <ver>`.
- **Schedule-based firewall rules.** The schedule tools (`create_firewall_schedule`, `create_schedule_time_range`, etc.) could build schedules, but no rule tool could reference one, so schedules were inert. `create_firewall_rule_advanced` and `update_firewall_rule` now expose a `schedule` parameter (sent as the API's `sched` field) to assign an existing schedule to a rule; on update, passing `""` detaches the schedule.
- **IPv6 / dual-stack firewall rules** (PR #10). `create_firewall_rule_advanced` exposes an `ipprotocol` parameter (`inet`, `inet6`, `inet46`) with validation instead of hardcoding `inet`.
- **uvx / pipx installation** (#8). Added a `pfsense-mcp-server` console entry point and setuptools package discovery, so the server can run without cloning the repository.

### Fixed

- **A momentary network blip or `503`/`429` failed the whole tool call.** The API client now retries transient failures with exponential backoff (capped): connection errors and `429`/`503` are retried for any method (a `Retry-After` header is honored, bounded); read-timeouts and `502`/`504` are retried only for idempotent `GET`s. Non-idempotent writes (POST/PATCH/DELETE) are never retried on an ambiguous read-timeout or gateway error, so a change can't be silently applied twice, and the fast-fail log endpoints (which set a short read timeout) opt out entirely. Also bounded the httpx connection pool (`max_connections=10`) so a burst of tool calls can't overwhelm pfSense's PHP-FPM workers.
- **The input sanitizer rejected legitimate values** (e.g. multi-container LDAP DNs like `CN=Users;DC=example,DC=com`, OpenVPN custom options, pipes in descriptions). Its shell-injection rules (`;\s*\w`, `|\s*\w`, backtick, `$(`, `${`) were security theater for this codebase — tool values are sent to the pfSense API as JSON *data*, never into a shell (the one real command sink is hard-allowlisted separately) — while false-positiving on real config. The denylist is now scoped to threats meaningful for stored data: path traversal and a `<script>` tag; field-level positive validation (IP/port/MAC/…) does the real input checking.
- **A failed rollback-point capture was silently swallowed.** For HIGH/CRITICAL operations the `@guarded` gate captures the pre-change config revision so the change can be undone, but a capture failure was `except: pass` — the operation proceeded with no rollback pointer and no warning, contradicting the "always backs up" docs. The tool result now carries a `config_backup_warning` when no rollback point could be captured.
- **`export_*` tools bypassed write-safety.** `export_certificate_pkcs12` (a private-key bundle) and `export_openvpn_client_config` were classified READ via the `export_` prefix and annotated `readOnlyHint=True`, so they were retained in `MCP_READ_ONLY` mode and skipped rate-limiting/audit despite issuing POSTs that extract secrets. They are now classified MEDIUM, `@rate_limited`, and annotated `readOnlyHint=False`.
- **The Docker HTTP-mode health check could never pass.** The Dockerfile and compose health checks probed `/mcp` unauthenticated, but the bearer-auth middleware 401s every request without a token — so a `streamable-http` container reported unhealthy forever. The middleware now answers an unauthenticated, secret-free `/health` (200), and the health checks point at it; `/mcp` still requires a valid bearer token.
- **Secrets could leak through echoed API error bodies.** On a 4xx, pfSense echoes the offending field values (which can include a submitted `password`/`pre_shared_key`/`ldap_bindpw`/`radius_secret`/…), and the full body was surfaced in the tool's error and logs. Error bodies are now run through the secret redactor before display, and a non-JSON error body is withheld entirely. The redactor's field list was widened from exact-match to include secret-indicating substrings, so provider-specific fields (`radius_secret`, `ldap_bindpw`, `ipsecpsk`, `authorizedkeys`, `webrootftppassword`, `cpanel_apitoken`, …) are caught without over-redacting public fields like `publickey`/`keylen`.
- **HTTP transport could boot with a publicly-known bearer token.** Startup previously rejected only an *empty* `MCP_API_KEY`, so a deployment left on the documented `CHANGE-ME` placeholder would run with a guessable token. It now also rejects placeholder values and tokens shorter than 16 characters (per key, for the comma-separated multi-key form).
- **33 mutating tools shipped with no guardrails at all** — no rate limiting, input sanitization, allowlist check, or audit trail. These included every `apply_*_changes` tool and `control_service` (which can stop `sshd`/`dhcpd`/`unbound`). All 33 now carry `@rate_limited`. A new registration-time meta-test (`tests/test_guardrail_coverage.py`) fails if any non-READ tool is undecorated or any HIGH/CRITICAL tool lacks the full `@guarded` confirm gate, so a forgotten decorator can no longer ship a silently-ungated tool. (The `@guarded`/`@rate_limited` decorators now carry a `_guardrail` marker for this check.)
- **Search tools missed matches beyond the first page.** 45 `search_*` tools filter their `search_term` client-side, but did so *after* server-side pagination — so a match on page 2+ was silently invisible and the returned `count` was wrong. A new `create_search_pagination` helper fetches the full window (up to the 200-object `MAX_PAGE_SIZE` cap) whenever a search term is active, so the filter sees every object; non-search listing is unchanged. (Configs larger than 200 objects of one type still only search the top 200 — the API's memory-safety cap.)
- **IPsec Phase 2 encryption entries could not be created.** The `IPsecPhase2Encryption` model has only `name` and `keylen`, but `create`/`update_ipsec_phase2_encryption` sent `encryption_algorithm_name`/`encryption_algorithm_keylen` plus phase1-only fields (`hash_algorithm`/`dhgroup`/`prf_algorithm`), so create 400'd on the missing required `name` and the extras were silently dropped. Now sends `name`/`keylen`; the phase1-only params are accepted for compatibility but no longer sent, and the search default sort moved to `name`. (The Phase 1/Phase 2 *create* tools require nested `encryption`/`hash_algorithm_option` proposal models that still need live validation before rebuild — tracked as a follow-up.) Verified against the pkg-RESTAPI v2.9.0 contract.
- **The OpenVPN tool family was non-functional and, worse, unsafe.** `create`/`update_openvpn_server` and `_client` sent `crypto` (upstream `data_ciphers`, an array), `ca`/`cert` (→`caref`/`certref`), `descr` (→`description`), `disabled` (→`disable`), and int `local_port`/`server_port`/`dh_length`/`proxy_port` where the upstream PortField/StringField want strings — so servers and clients could not be created. Two of these were security-relevant: a dropped `disabled` created a **live** VPN listener when the caller asked for a disabled one, and `manage_openvpn_cso` sent `server_id` (upstream `server_list`, an array of interface names) which, when dropped, silently applied the client-specific override to **all** servers. `compression` is mapped to `allow_compression` (`no`/`yes`/`asym`), `custom_options`/`local_network`/`remote_network` are sent as arrays, `redirect_gateway`→`gwredir`, and every OpenVPN search filtered/sorted on `descr` (a nonexistent field that matched everything) — now `description`. `export_openvpn_client_config` used all-wrong field names (`server`/`type`/`usetoken`/`silent` upstream); the mappable fields are corrected (some export knobs still need live validation). Verified field-by-field against the pkg-RESTAPI v2.9.0 contract.
- **WireGuard peers and tunnels were misconfigured or rejected.** Peers sent `keepalive` (upstream field is `persistentkeepalive`), referenced their tunnel by array-index `id` instead of by name (`tun` is a name reference upstream), and sent `port`/`listenport` as integers where the upstream PortField is string-typed. New peers were also created without `enabled`, which defaults to *false* upstream — so an MCP-created peer was inert until separately enabled. `create`/`update_wireguard_peer` and `create`/`update_wireguard_tunnel` now send `persistentkeepalive`, tunnel names, string ports, and an explicit `enabled` (default True). Verified against the pkg-RESTAPI v2.9.0 contract.
- **User groups and LDAP auth servers could not be configured.** Groups sent `descr` (upstream field is `description`) and `member` as array-index user IDs (upstream references users by **name**), so descriptions and membership never took. LDAP auth-server tools sent generic `port`/`transport`/`scope`/`basedn`/`authcn` with a `tcp`/`ssl`/`starttls` transport vocabulary; upstream uses `ldap_port`/`ldap_urltype`/`ldap_scope`/`ldap_basedn`/`ldap_authcn` with url-type values `Standard TCP`/`STARTTLS Encrypt`/`SSL/TLS Encrypted`, and the port fields are string-typed — so LDAP servers could never be created. All corrected (tool parameter names unchanged); RADIUS auth-server ports are likewise coerced to strings.
- **Certificate & CA import, renewal, and PKCS#12 export were all non-functional.** Import sent `cert` (upstream field is `crt`) plus an unknown `method` key, so `create_certificate`/`create_certificate_authority` 400'd; internal generation was POSTed to the *import* endpoint, where its key/DN fields were silently dropped. `create_certificate`/`create_certificate_authority` now route `method="import"` to the import endpoint (`crt`/`prv`) and `method="internal"` to `/generate` (with a new `ecname` parameter, required for ECDSA); `update_certificate`/`update_certificate_authority` send `crt`; `generate_certificate` drops the bogus `method` and sends `ecname` for ECDSA keys. `renew_certificate` and `export_certificate_pkcs12` sent the non-persistent array index as `id`, but both endpoints key on `certref` (the certificate's stable refid) — they now resolve the refid first. Verified field-by-field against the pkg-RESTAPI v2.9.0 contract.
- **Boolean search filters returned inverted results.** `QueryFilter` serialized Python bools with `str()`, yielding `"True"`/`"False"`; the pfSense query engine only coerces the lowercase `true`/`false` to booleans and loose-compares everything else as truthy. So `search_firewall_rules(disabled=False)` — "show enabled rules" — returned exactly the *disabled* rules. `QueryFilter.to_param` now lowercases booleans, fixing the whole class at the root.
- **`search_services(status_filter="stopped")` returned the running services.** `Service.status` is a boolean upstream, so the string `"stopped"` loose-matched everything; `find_running_services`/`find_stopped_services` now filter on real booleans (`True`/`False`).
- **`MCP_READ_ONLY=true` crashed the server at startup** (regression from the FastMCP 3.4.6 upgrade). The read-only tool reduction reached into FastMCP 2's private `mcp._tool_manager._tools`, which FastMCP 3 removed, so the documented least-privilege mode raised `AttributeError` and would not start. It now uses FastMCP's public `mcp.local_provider` API (`list_tools` / `remove_tool`), producing the same 130 read-only tools. The reduction also moved out of module-import scope into `main()` (as `apply_read_only_filter()`): doing async work while the module was still importing could deadlock against Python 3.11's import lock. Added `tests/test_read_only_mode.py`, which runs the filter in isolated subprocesses (hard timeout, hermetic env) so neither the crash nor the hang can regress silently.
- **`src.__version__` reported `5.0.0`** while every other version string (`pyproject.toml`, `server.py`, `Dockerfile`) said `1.0.0`. `src/__init__.py` now derives `__version__` from `server.VERSION`, single-sourcing the two.
- **DNS Resolver DHCP registration was a silent no-op.** `update_dns_resolver_settings` mapped `register_dhcp`/`register_dhcp_static` to themselves, but the upstream fields are `regdhcp`/`regdhcpstatic`; PATCH silently dropped the unknown keys and reported success. Now mapped correctly (tool parameter names unchanged).
- **DHCP DNS-server override always failed.** `create_dhcp_static_mapping` and `update_dhcp_server_config` sent `dnsserver` as a bare string, but upstream it is an array of up to 4 strings. The tools now accept one value or a comma/space-separated list, validate each as an IP, and send an array.
- **DNS Resolver access-list tools could not create or update.** They sent `aclname`/`aclaction`/`descr` (internal-only names) with underscore action values; upstream uses `name`/`action`/`description` with space-separated actions (`allow snoop`, `deny nonlocal`, `refuse nonlocal`). Create 400'd; update silently no-op'd. The tools keep their ergonomic parameter names/spellings and map to the wire values; `search_dns_access_lists` default sort moved from `aclname` to `name`.
- **`remove_from_alias` failed on aliases with per-entry descriptions** (400 `TOO_MANY_ALIAS_DETAILS`). The API's remove control flag strips only `address` entries, leaving the parallel `detail` list longer than the address list, which the API then rejects. `manage_alias_addresses(action="remove")` now reads the alias and rebuilds both lists in lockstep before PATCHing.
- **`create_firewall_schedule` could not actually create a schedule.** The pfSense API requires at least one time range at creation ("Field `timerange` is required"), but the tool never sent one. It now takes `hour`/`position`/`month`/`day`/`rangedescr` for the initial time range (further ranges via `create_schedule_time_range`) and validates that either `position` (weekdays) or `month`+`day` is provided. Also corrected `month`/`day`/`position` on `create_schedule_time_range`/`update_schedule_time_range` from `str` to `List[int]` to match the API schema, with docstrings explaining pfSense's semantics (`position` = weekday numbers 1–7). Verified end-to-end against a live pfSense 26.03 instance.
- **`create_acme_certificate` could not actually create a certificate.** The pfSense API rejects certificates with no domain/SAN entries ("Field `a_domainlist` is required"), but the tool never exposed that field. Added a required `a_domainlist` parameter (and an optional one on `update_acme_certificate` to replace the whole list); added `search_acme_certificate_domains` and `manage_acme_certificate_domain` to read and incrementally add/remove individual domain entries (DNS-01 via a provider API, HTTP-01, webroot, etc.) without resending the whole array.
- **`issue_acme_certificate`/`renew_acme_certificate` always failed** ("Field `certificate` is required"). Both endpoints key off the certificate's `name`, not the array-index `id` the tools took as input. They now resolve `id` → `name` internally and send the correct field, with no change to the tools' own `id` parameter.
- **ACME issuance could hang forever with no error on networks that block DNS-over-HTTPS.** Without `dnssleep`, acme.sh polls public DoH resolvers (`cloudflare-dns.com`, `dns.google`, etc.) to self-check DNS-01 propagation before contacting Let's Encrypt; if those are blocked (a common DNS-hardening setup), the check loops every 10 seconds indefinitely and the REST API reports `status: pending` forever with an empty log. Reproduced live against a real pfSense instance — confirmed via SSH that the underlying `acme.sh` process was alive but stuck in that retry loop. Added `dnssleep` to `create_acme_certificate`/`update_acme_certificate` to skip the check and just wait a fixed number of seconds instead.
- **`create_haproxy_frontend`/`update_haproxy_frontend` silently dropped bind addresses.** They sent a `bind_addresses` field that doesn't exist in the pfSense API; the real field is `a_extaddr`. Fixed the outgoing field name (the tool's own `bind_addresses` parameter is unchanged) and added `ssloffloadcert`/`ha_certificates` so a frontend's SSL certificate can actually be set — previously there was no way to bind a cert to a frontend at all. Added `search_haproxy_frontend_addresses`/`manage_haproxy_frontend_address` and `search_haproxy_frontend_certificates`/`manage_haproxy_frontend_certificate` for incremental add/remove of individual bind addresses and SNI certificates.
- **All `delete_*` tools were non-functional** (#12, PR #9, PR #16). `httpx.AsyncClient.delete()` does not accept a `json=` kwarg, so every delete (firewall rules, NAT, aliases, DHCP mappings, etc.) raised `TypeError` before any HTTP traffic. DELETE now routes through `client.request("DELETE", ...)`, which supports the JSON body pfSense requires.
- **`update_log_settings` could not enable remote syslog and silently dropped fields** (#13, PR #11). The wire-format keys `ipproto` and `reverse` were ignored by the API; renamed to `ipprotocol` and `reverseorder`. Added `enableremotelogging` (the master toggle), `logconfigchanges`, and the per-category remote-syslog toggles (`auth`, `portalauth`, `vpn`, `dpinger`, `hostapd`, `system`, `resolver`, `ppp`, `routing`, `ntpd`).
- **`update_webgui_settings` could not change the WebGUI port** (#7). The pfSense REST API requires `port` as a string; the tool now accepts an `int` for ergonomics and coerces it to a string before sending.
- **Log endpoints could hang until pfSense ran out of memory** (PR #6). Added a 10-second read-phase timeout and classification of read-phase failures (`ReadError`/`RemoteProtocolError`/`ReadTimeout`) into a clear, actionable message (upstream tracking: pfSense-pkg-RESTAPI#806), with docstring warnings on the log tools.
- **Transient connectivity blip at launch killed the server** (PR #14). A momentary preflight failure before the stdio channel opens now logs a warning and starts anyway; individual tools surface connectivity errors when invoked.

### Security

- The secret redactor's exact-name/substring matching missed short provider credential fields like `cf_token`/`cf_key` in the new open-ended ACME `provider_fields`/`a_domainlist` dicts (DNS provider API tokens/keys — pfSense's ACME package alone has ~250 possible field names), which would have shown raw secrets in approval requests and audit logs. Added a narrow suffix check (`_key`, `_token`, `_secret`, `_password`, `_passwd`, `_pwd`) so these are redacted without over-redacting identifiers like `certificate_id` or `cf_zone_id`.

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
