# Deep System Audit & Next-Release Plan (v2)

> **Status (2026-08-08):** this is a **point-in-time audit** of `main` @ 8a27acd;
> most of its P0/P1 items have since landed on `main` — the W-0 contract-test
> layer, the `MCP_READ_ONLY` hotfix, the OpenVPN/certificates/users/LDAP/DNS-ACL
> wire rebuilds, the query-inversion and search-pagination fixes, guardrail
> coverage enforcement (meta-test), Docker `/health`, SECURITY.md, error-body
> redaction, retry/backoff, and the CI matrix + coverage gate (see
> [CHANGELOG](CHANGELOG.md) *Unreleased*). Still open: the IPsec Phase 1/2
> nested-proposal create rebuild, a typed exception hierarchy, annotation-driven
> risk classification, and the v2.0 package rename / PyPI / multi-instance work.
> Section-level findings below describe the state **at the audited revision**,
> not necessarily current `main`.

**Subject:** pfSense MCP Server
**Audit date:** 2026-08-06 — supersedes the 2026-06-26 audit (see git history for v1)
**Audited revision:** `main` @ 8a27acd (post PRs #19–#28: HAProxy/alias/DNS/schedule wire fixes, fastmcp 2.14.0→3.4.6, pfSense version matrix for Plus 26.03.1 / pkg-RESTAPI v2.9.0)
**Method:** Six independent verification passes (VPN wire-format, DHCP/DNS/certs/users wire-format, query/filter semantics, security & guardrails, client architecture, testing/CI/packaging/docs). **Every wire-format claim was verified against the actual upstream model source** — `pfrest/pfSense-pkg-RESTAPI` at tag **v2.9.0** (`RESTAPI/Models/*.inc`, `Core/Model.inc`, `Core/Field.inc`, `Core/ModelSet.inc`, `ContentHandlers/URLContentHandler.inc`) — eliminating the v1 audit's "(verify)" caveats. Runtime claims were exercised live against the installed fastmcp 3.4.6. No code was changed by this audit.

---

## 1. Executive summary

Since the v1 audit, ten PRs landed: real wire-format fixes (HAProxy fields, alias detail lockstep, firewall schedules, DNS resolver bindings, delete-JSON), the fastmcp 3.4.6 upgrade with a CI probe proving forward compatibility with MCP spec 2026-07-28, and a refreshed pfSense/pkg-RESTAPI version matrix. Tests grew 308→337; coverage 17%→26%; CI gained lint and a forward-compat job.

**The upstream-source verification changed the picture substantially, in both directions:**

- **Nine v1 suspicions were REFUTED** — the code was already correct (DHCP lease times, flat `range_from/to`, interface `subnet` int, certificate `keylen`/`lifetime` ints, IPsec int enums, IPsec `cert` auth vocabulary, WG separate `port` field, `parent_id` int filters). These are struck from the work list.
- **The confirmed + newly-found bug set is far worse than v1 estimated in three families.** The **OpenVPN/IPsec tool family is essentially nonfunctional** against v2.9.0 (§3.1). The **certificate import/renew/export, LDAP auth-server, DNS access-list, and user-group tools cannot succeed at all** (§3.2). And the query layer has **silently inverted results** — `search_firewall_rules(disabled=False)` returns exactly the disabled rules; `find_stopped_services` returns the running ones (§3.3).
- **One regression was introduced by the fastmcp 3 upgrade (PR #27):** `MCP_READ_ONLY=true` now crashes at startup (`main.py:58` reaches into fastmcp 2's removed `_tool_manager`). It fails closed, but the documented least-privilege mode is unusable. This is exactly the fragility v1 flagged as P2 ("read-only mode mutates FastMCP private internals"); it is now a **P0 hotfix**.

Three upstream framework facts (all verified in v2.9.0 source) explain why this bug class is invisible at runtime and must anchor the fix strategy:

1. `Model::from_representation` **silently ignores unknown request keys** → a misnamed field on PATCH is a no-op that reports `success: true`.
2. `Field::check_field_type` is **strictly typed** (`gettype($value)` must match) → an int sent to a `PortField`/`StringField` hard-400s. On POST, missing required fields 400.
3. `ModelSet::query()` **skips filters on nonexistent fields** (returns everything) and `ExactQueryFilter` uses PHP **loose `==`** (any non-empty string, including `"False"`, equals `true`) → wrong filter names/types degrade to unfiltered or inverted results, never errors.

**Consequence:** hand-auditing tool-by-tool will keep missing these. The systemic fix is a **contract-test layer against the upstream schema** — v2.9.0 releases ship `openapi.json` as a release asset; vendor it and assert in tests that every payload key/type a tool sends exists on the target model (§7, W-0). This one mechanism would have caught ~30 of the findings below at test time.

---

## 2. Current-state snapshot

| Dimension | Measure |
|---|---|
| Source | 34 tool modules, **327 registered tools** (count verified via live `list_tools()`) |
| Tests | **337 passing**, coverage **26%**; 11 of 34 tool modules have tests, 23 at 0% |
| MCP stack | fastmcp `>=3.4.6,<4.0` + mcp `>=1.24,<2.0`; speaks MCP 2025-11-25, negotiates down; suite passes on fastmcp 4.0.0b1 (spec 2026-07-28) via non-blocking CI probe |
| pfSense targets | CE 2.8.1, Plus 25.11.1/26.03/26.03.1 (pkg-RESTAPI v2.9.0); legacy CE 2.8.0/Plus 24.11/25.11 (pkg v2.7.3) |
| CI | test (3.11) + ruff + fastmcp-4-beta probe; no matrix/coverage gate/security scan/release automation |
| Guardrails | `@guarded` on delete/power tools; **33 mutating tools have no decorator at all**; enforcement is per-tool opt-in |
| Distribution | Docker hardened but HTTP healthcheck can never pass; not PyPI-publishable (`src` package name) |

**Severity legend:** **P0** release blocker · **P1** must-fix for a credible release · **P2** should-fix · **P3** polish.

---

## 3. Wire-format findings (verified against v2.9.0 model source)

### 3.1 VPN family — P0 cluster: OpenVPN/IPsec tools nonfunctional

Every finding cites the local send site and the upstream field definition.

| Sev | Tool(s) | Defect | Upstream contract |
|---|---|---|---|
| **P0** | `create_openvpn_server` | Cannot succeed: missing required `caref`/`certref` (sends `ca`/`cert` — dropped), `data_ciphers`/`data_ciphers_fallback` (sends `crypto` — no such field), `ecdh_curve` (never sent), `dh_length` sent as int (StringField → 400). Docstring `mode=p2p_shared_key` no longer exists upstream. | `OpenVPNServer.inc` L129–266 |
| **P0** | `create_openvpn_client` | Cannot succeed: missing required `mode` (`p2p_tls`), `caref`, `data_ciphers*`; `server_port` int vs PortField-string. | `OpenVPNClient.inc` L106–269 |
| **P0** | `create_ipsec_phase1` | Always 400s: required `encryption` (NestedModelField), `myid_type`, `peerid_type` never sent; `caref`/`certref` (required when `authentication_method=cert`) not exposed — cert-based P1 impossible. | `IPsecPhase1.inc` L118–266 |
| **P0** | `create_ipsec_phase2` | Always 400s: required `encryption_algorithm_option` + `hash_algorithm_option` never sent; `localid_type=none` (documented) is invalid. | `IPsecPhase2.inc` L97–235 |
| **P0** | `create/update_ipsec_phase2_encryption` | Sends 5 keys; upstream model has exactly 2 (`name`, `keylen`). Create 400s, update silently no-ops. `hash_algorithm`/`pfsgroup` actually belong on IPsecPhase2. | `IPsecPhase2Encryption.inc` L31–38 |
| **P0** | `export_openvpn_client_config` | Wholly mismatched: sends `server_id`/`export_type`/`hostname`/…; upstream requires `server` + `type` (`confzip`/`confinline`/`inst-Win10`/…). Every call 400s. | `OpenVPNClientExport*.inc` |
| **P0** | VPN int-port cluster | OpenVPN `local_port`/`server_port`/`proxy_port`, WG tunnel `listenport`, WG peer `port` all sent as int; every one is a PortField (string) → hard 400. Same class PR #19 fixed for HAProxy — never applied to VPN. | `Fields/PortField.inc` L115 |
| **P1** | OpenVPN family `disabled` → `disable` | **Security-relevant silent drop:** "create disabled" creates an enabled, live VPN listener; "disable this server/CSO" no-ops with success. | Server L135 / Client L112 / CSO L62 |
| **P1** | `manage_openvpn_cso` `server_id` → `server_list` | **Security-relevant:** dropped key + upstream default `[]` = "applies to ALL servers" — a per-server override (static IP, block) silently goes fleet-wide. Search filter `server_id` also matches nothing. | `OpenVPNClientSpecificOverride.inc` L81 |
| **P1** | OpenVPN family `descr` → `description` | All creates/updates drop the description; all OpenVPN search/sort on `descr` filters on a nonexistent field (returns everything). WireGuard/IPsec correctly use `descr`. | Server L129 etc. |
| **P1** | WG peer `keepalive` → `persistentkeepalive` | Silently dropped — NAT-traversal keepalive can never be set. | `WireGuardPeer.inc` L74 |
| **P1** | WG peer `tun` sends tunnel id (int) | Upstream is a ForeignModelField on tunnel **name** (`"tun_wg0"`) → 400/no-match. | `WireGuardPeer.inc` L47 |
| **P1** | WG tunnel `name` on create/rename | Upstream name is system-assigned/read-only; rename throws `FIELD_VALUE_CHANGED_WHEN_NOT_EDITABLE`. | `WireGuardTunnel.inc` L40–44 |
| **P2** | `compression` → `allow_compression` (`no/yes/asym`); WG peers default `enabled=false` (tool exposes no `enabled` param → peers created inert). | | |

**Refuted (correct as-is, do not "fix"):** WG separate `port` field design; IPsec `dhgroup`/`encryption_algorithm_keylen` as ints; IPsec `cert` auth vocabulary.

### 3.2 Certificates / users / DNS — P1 cluster: whole workflows broken

| Sev | Tool(s) | Defect | Upstream contract |
|---|---|---|---|
| **P1** | `create/update_certificate`, `create/update_certificate_authority` (import) | Sends `cert`; field is `crt` (required) → import 400s, update silently drops the new cert body. | `Certificate.inc` L71, `CertificateAuthority.inc` L74 |
| **P1** | `create_certificate(method="internal")`, `create_certificate_authority` | Phantom generation path: keytype/keylen/digest/lifetime/dn_* don't exist on the import models (silently ignored). Internal generation lives at `/system/certificate/generate` + `/system/certificate_authority/generate`; **no CA-generate tool exists at all**. | model field lists |
| **P1** | `renew_certificate`, `export_certificate_pkcs12` | Send `{"id": <array index>}`; upstream requires `certref` (refid string) → both always 400. | `CertificateRenew.inc` L29, `CertificatePKCS12Export.inc` L26 |
| **P1** | `create/update_user_group` | `member: List[int]` ("user IDs") — upstream takes **usernames** (ForeignModelField on `name`, many); `descr` → `description`. Group membership/description can never be set. | `UserGroup.inc` L60–80 |
| **P1** | `create_auth_server` (LDAP) | Sends `port`/`transport`/`scope`/`basedn`/`authcn`; upstream: `ldap_port` (required), `ldap_urltype` (required; choices `'Standard TCP'`/`'STARTTLS Encrypt'`/`'SSL/TLS Encrypted'`), `ldap_scope`, `ldap_basedn`, `ldap_authcn`. LDAP creation impossible; RADIUS path is fine. | `AuthServer.inc` L86+ |
| **P1** | DNS resolver `register_dhcp`/`register_dhcp_static` | Map to themselves; upstream fields are `regdhcp`/`regdhcpstatic` → silent no-op with success. | `DNSResolverSettings.inc` L150–159 |
| **P1** | DNS access-list tools | Send internal names `aclname`/`aclaction`/`descr`; representation fields are `name`/`action`/`description`; action choices use spaces (`'allow snoop'`) vs local underscore validation. Create 400s; update silently no-ops; `sort_by="aclname"` invalid. | `DNSResolverAccessList.inc` L29–48 |
| **P1** | DHCP `dnsserver` (2 sites: static mapping + server config) | Sent as bare string; upstream is `many=true` array (max 4) → validation failure. | `DHCPServer.inc` L167, `DHCPServerStaticMapping.inc` L119 |
| **P2** | `authorizedkeys` docstring says base64 — representation is plain text (double-encodes); DNS resolver settings missing `port`/`enablessl`/`sslcertref`/`tlsport`/`outgoing_interface`/`strictout`/`regovpnclients`; ECDSA cert generation lacks required `ecname`. | | |

**Refuted:** DHCP lease times as int; flat `range_from`/`range_to`; interface `subnet` int; certificate `keylen`/`lifetime` ints. Host/domain-override, CRL, and user-expiry formats verified clean.

### 3.3 Query/filter semantics — silent inversions

| Sev | Finding | Mechanism |
|---|---|---|
| **P1** | `search_firewall_rules(disabled=False)` returns **exactly the disabled rules** (inverted); `disabled=True` works by accident. | `QueryFilter.to_param` yields `"True"`/`"False"`; upstream `infer_type` only lowercases `"true"`/`"false"` to bool; loose `==` casts any non-empty string to `true`. Fix at the root: lowercase bools in `models.py to_param` (`vpn_wireguard.py:52` already does it per-site). |
| **P1** | `find_stopped_services` returns the **running** services. | Sends `QueryFilter("status","stopped")`; `Service.status` is a BooleanField; `"stopped"` loose-equals `true`. |
| **P1** | `server_id` filters in 3 `vpn_advanced` search tools + CSO search `descr`/`server_id` are **silent no-ops** (return everything). | `ModelSet::query()` skips nonexistent fields. |
| **P1** | **35 search tools** filter `search_term` client-side *after* server-side pagination — matches beyond page 1 silently missed, `count` misreports. Full list in agent pass (21 files); +1 variant (`search_services` implicit limit=200). | |
| **P2** | `QueryFilter` accepts `Any` and bare-`str()`s it — the root enabler of the bool bug class. | `models.py:36,54` |

---

## 4. Security & guardrails (all v1 findings re-verified: 9/9 still open, plus new)

| Sev | Finding | Reference |
|---|---|---|
| **P0** | **`MCP_READ_ONLY=true` crashes at import** — `main.py:58` uses fastmcp 2's `_tool_manager._tools`, removed in fastmcp 3.4.6 (`AttributeError`, reproduced). Fail-closed, but the documented least-privilege mode is unusable and no test covers it. Fix: `mcp.local_provider.remove_tool()` / filtered registration + a CI test that boots read-only mode. | `main.py:56-67`; regression from PR #27 |
| **P0** | **33 mutating tools carry no guardrail decorator** (no rate-limit/sanitize/allowlist/audit): all 11 `apply_*_changes`, `control_service` (can stop sshd/dhcpd/unbound), 9 delete-capable `manage_*` (also mis-annotated `destructiveHint=False`), `move_firewall_rule`, cert generate/renew, ACME issue/renew/register, WoL, HATEOAS toggles (annotated `destructiveHint=True` yet undecorated). | AST scan; cites in agent pass |
| **P0** | **Confirm gate still opt-in per tool** — no registration-time enforcement, no meta-test; `manage_openvpn_cso` hand-rolls confirm on delete only. Prefix-based risk classification compounds it: `manage_*` = MEDIUM, so even `@guarded` wouldn't confirm-gate their deletes. | `guardrails.py:46-105,687` |
| **P1** | Secrets leak via echoed 4xx bodies (full `response.text` into error string → tool output + logs). | `client.py:271-301` |
| **P1** | Rollback capture still `except Exception: pass`; `CHANGE-ME` placeholder key accepted; in-memory rate limiter. | `guardrails.py:733-749`; `main.py:159-165` |
| **P2** | Exact-match redaction list (misses `radius_secret`, `ldap_bindpw`, `ipsecpsk`, `authorizedkeys`); `export_*` classified READ (PKCS12 private-key export survives read-only mode — moot while read-only crashes); missing-Origin allowed (documented tradeoff needed); naive regex denylist sanitization; `manage_alias_addresses` remove path is GET-then-PATCH whole-list rewrite (TOCTOU) with no guardrails. | as cited |

---

## 5. Client & architecture (re-verified)

| Sev | Finding | Reference |
|---|---|---|
| **P0** | Bare `Exception` with multi-line strings; 359 stringly-typed `except Exception` tool handlers; 5 substring checks (`"401" in str(e)`). No typed hierarchy. | `client.py:292-301,1202-1209`; `tools/dhcp.py:181` |
| **P0** | No retry/backoff; 429/`Retry-After` ignored. | `client.py:250-301` |
| **P1** | JWT: no refresh lock, hardcoded 1h expiry (ignores real `exp`), no 401-retry. No `httpx.Limits`. Full-body buffering outside log endpoints. Global singleton + preflight close/reset dance (mitigated by `_ensure_client` loop guard). | `client.py:76-136,272-305`; `server.py:45-105` |
| **P2** | `MCP_ALLOWED_TOOLS` gates only non-READ tools and doesn't hide tools from `tools/list` — document. | `guardrails.py:465-483` |
| **P3** | `src/__init__.py` `__version__="5.0.0"` vs 1.0.0 in pyproject/server.py/Dockerfile — active mismatch; single-source it. `mcp.remove_tool` deprecation; optional migration of Origin checks to `http_app(allowed_origins=...)`. | `src/__init__.py:6` |

**fastmcp 3 migration residue: clean otherwise** — `FastMCP(version=)`, `run()`, `http_app()`, ToolAnnotations imports, middleware composition all verified against installed 3.4.6; 327 tools register; the read-only block is the only breakage.

---

## 6. Testing / CI / packaging / docs / ops (re-verified)

| Sev | Finding |
|---|---|
| **P0** | `src` top-level package name — PyPI blocker (unchanged). No SECURITY.md (unchanged). Version mismatch (see §5 P3 — promoted: it's user-visible via `__version__`). |
| **P1** | **Docker HTTP healthcheck can never pass**: Dockerfile + compose probe `/mcp` unauthenticated; `BearerAuthMiddleware` 401s everything → container permanently unhealthy in HTTP mode. Add an exempt `/health` endpoint. |
| **P1** | Coverage 26%; 23/34 tool modules at 0% (top movers: troubleshoot 670 stmts, pkg_haproxy, vpn_openvpn, routing, users, vpn_ipsec, interfaces, vpn_wireguard, certificates, traffic_shaper). CI: no 3.12/3.13 matrix (dev runs 3.13, CI 3.11!), no pip-audit/bandit/dependabot, no release automation, no coverage gate. pyproject missing PyPI metadata; no lockfile; httpx pin divergence. |
| **P1** | CRUD gaps (unchanged): bridges/groups update+delete; DNS forwarder settings update; IPsec phase1-encryption update. |
| **P2** | Docs drift: README badges "323 tests" (→337) and "API v2.7.3" (→v2.9.0); PFSENSE_API_AUDIT.md stamped v2.7.3/March 2026; `mcp.json` ships `CE_2_8_0` + bare `python3` (3.9 on many systems); `.dockerignore` misses `build/`/`dist/`/`*.egg-info`/`.venv` (144 MB build context). No issue/PR templates. |

---

## 7. Consolidated must-fix list

**W-0 (systemic, do first):** vendor upstream v2.9.0 `openapi.json` (shipped as a release asset) and add a **contract-test layer**: for every tool, assert each payload key exists on the target model with the right JSON type, and each QueryFilter field exists on the queried model. This converts the silent-drop / strict-type / skip-filter bug class into red tests. (~30 of the findings above would have been caught.)

**P0 — gate the next release**
1. Hotfix `MCP_READ_ONLY` for fastmcp 3 + boot test (ship immediately as 1.0.x).
2. Rebuild the OpenVPN/IPsec create/update/export tools against the real v2.9.0 contracts (§3.1) — including the two security-relevant silent drops (`disable`, CSO `server_list`) and the VPN int-port cluster.
3. Fix certificates import/renew/export (`crt`, `certref`), add real generate endpoints (incl. CA generate), fix user-group membership, LDAP auth-server, DNS ACL, `regdhcp*`, `dnsserver` array (§3.2).
4. Fix inverted queries at the root (`to_param` bool lowercasing), `find_stopped_services`, no-op filter fields (§3.3).
5. Guardrails: decorate the 33 unguarded mutating tools; enforce gate coverage at registration with a meta-test; make risk classification annotation-driven.
6. Docker `/health` endpoint; version single-sourcing; SECURITY.md.

**P1 — credible release**
7. Pagination-aware `search_term` (server-side `descr__contains` or fetch-all-then-filter) across the 35 affected tools.
8. Error-body secret redaction; typed exceptions + retry/backoff + 429.
9. CI matrix (3.11–3.13) + pip-audit + dependabot + coverage gate; PyPI metadata + lockfile.
10. CRUD gaps; README/docs re-stamp; `.dockerignore`; `mcp.json` fix.

**P2** — suffix-based redaction, export_* reclassification, missing-Origin documentation, JWT/pool/buffering hardening, TOCTOU note on alias rewrite, issue/PR templates.

---

## 8. Release plan (revised)

- **v1.0.1 — "Hotfix" (immediately):** MCP_READ_ONLY fastmcp-3 fix + boot test; version-string fix; README badge corrections. Nothing else.

- **v1.1.0 — "Wire truth" (the big correctness release):** W-0 contract-test layer first, then every §3 fix lands red-test-first against it (VPN family rebuild, certificates/users/LDAP/DNS-ACL cluster, query inversions, `dnsserver`, `regdhcp*`), plus the 35-tool search fix and CRUD gap fills. Every fix ships with a contract test asserting the exact keys/types sent. This is the release that makes the "327 tools" claim true — today a material fraction of the VPN/cert/user surface cannot work at all.

- **v1.2.0 — "Trustworthy safety":** registration-enforced guardrails (decorate all 33 + meta-test), annotation-driven risk, error-body redaction + suffix redaction list, honest rollback, placeholder-key rejection, `export_*` reclassification, SECURITY.md + threat model, Docker `/health`, missing-Origin documentation. Re-frame safety docs to match enforcement reality.

- **v2.0.0 — "Production platform" (breaking):** package rename → `pfsense_mcp_server` + PyPI publish + release automation; typed-exception/retry/429 client rewrite; singleton → factory (multi-instance); JWT/pool/buffering hardening; CI matrix + security scanning; coverage ≥60% with the contract suite as the backbone; fastmcp 4 flip when stable (CI probe already green → MCP spec 2026-07-28 with per-connection backward compatibility).

- **vNext — "Coverage expansion":** Snort/Suricata, pfBlockerNG, Captive Portal, GRE/GIF/LAGG, DHCPv6/RA, DDNS — each built on the contract-validated wire layer, never before it.

**Sequencing rationale:** the contract layer precedes all wire fixes (it is how each fix is proven and how regressions are prevented); correctness precedes safety marketing; safety precedes the breaking platform release; new coverage only on the validated foundation.

---

*Verification provenance: upstream contracts read from `pfrest/pfSense-pkg-RESTAPI` @ v2.9.0 — `Core/Model.inc` (silent-drop, L1191-1197), `Core/Field.inc` (strict types, L780), `Core/ModelSet.inc` (skip-unknown-filter), `ContentHandlers/URLContentHandler.inc` (`infer_type`), `QueryFilters/ExactQueryFilter.inc` (loose `==`), and the individual `Models/*.inc` cited inline. Local line references are against `main` @ 8a27acd.*
