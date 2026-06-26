# Deep System Audit & Next-Release Plan

**Subject:** pfSense MCP Server
**Audit date:** 2026-06-26
**Audited revision:** `main` @ post-1.0.0 (after PRs #6/#9/#10/#11/#14/#15/#16/#17)
**Method:** Read-only static audit across four independent deep-read passes (core architecture, security & guardrails, tool coverage & wire-format fidelity, testing/CI/packaging/ops), each citing `file:line`, followed by spot-verification of headline findings against the code. **No code was changed.**

> **Confidence note.** Findings about *what the tool sends* are confirmed against the code (line-referenced). Findings about *what the pfSense REST API expects* (field names/types) are reasoned from the pfSense REST API v2 model contract and are marked **(verify)** where they should be confirmed against the installed model `.inc` schema before any fix. The repository has **no schema-validation layer**, so these mismatches are invisible at runtime — the single most important systemic theme of this audit.

---

## 1. Executive summary

The project is a genuinely capable v1.0.0: 327 tools across 34 modules, ~21.7k LOC, a thoughtful CRUD/HATEOAS client that handles real pfSense REST API v2 quirks, a working confirm-gate for destructive operations, fail-closed HTTP auth, and green CI. It is solid as a single-process, single-firewall, stdio-transport tool driven by a trusted operator.

For a **next major release**, three themes dominate:

1. **Correctness (highest value): wire-format fidelity.** The same bug class as the just-fixed #7/#13 (a tool sends a field name or scalar/array/int/str shape the pfSense model silently drops, yet returns `success: true`) exists in **at least a dozen more places**, several **P0** in OpenVPN, WireGuard, and DHCP. These produce "successful but misconfigured" firewall/VPN objects — the most dangerous outcome for an LLM-driven tool. A startup field-name validation layer would have caught #7, #13, and most of these mechanically.

2. **Safety credibility: close the guardrail gaps.** The "9-layer defense-in-depth" headline is realistically ~3 load-bearing layers. Risk classification is **name-based and fragile**, the confirm gate is **opt-in per-tool** (so a forgotten decorator silently ships an un-gated destructive tool — and several `manage_*`/`control_service` tools already have **no guardrail decorator at all**), secrets can **leak through echoed API error bodies**, and config-backup/rollback **silently no-ops on failure** while the docs claim it always runs.

3. **Productionization: architecture, distribution, and test depth.** The HTTP client has **no retry/backoff**, **no 429 handling**, **bare-`Exception` error typing**, and a **module-global singleton** that blocks multi-instance and clean testing. Real tool-layer test coverage is **~17%** (270 of 327 tools untested). The package can't ship to PyPI as-is (top-level package literally named `src`). There is **no SECURITY.md** on a firewall-management tool, and the `CHANGE-ME` placeholder API key is not rejected at startup.

None of these are emergencies for the current stdio/single-operator use case, but each is a gate for a credible "big release" that markets safety and broad coverage.

---

## 2. Current-state snapshot

| Dimension | Measure |
|---|---|
| Source | ~21,673 LOC, 34 tool modules, 327 registered tools (130 read-only) |
| Tests | 323 passing; ~17% of tools exercised; only 9 of 35 modules have tool tests |
| CI | Green; single Python (3.11); no matrix, coverage gate, security scan, or release automation |
| Guardrails | `@guarded` confirm gate on ~52 destructive tools; `@rate_limited` on ~112; both **opt-in per tool** |
| Deps | `fastmcp==2.14.0` (exact), `httpx` (unpinned in pyproject); no lockfile |
| Tech debt markers | 4 TODOs (all the tracked log-OOM workaround) |
| Distribution | Docker (well-hardened); pip/uvx entry point works locally; **not PyPI-publishable** as-is |

**Severity legend:** **P0** release blocker / correctness or safety hole · **P1** must-fix for a credible major release · **P2** should-fix · **P3** polish/hardening.

---

## 3. Section A — Wire-format fidelity (the next #13) — *highest value*

The failure mode: a field name/type the pfSense model doesn't recognize is **silently dropped**; the tool still returns `success: true`; the object is created/updated **misconfigured**. All locations are confirmed in code; the pfSense-side expectation is marked **(verify)** where it needs schema confirmation.

| Sev | Location | What the tool sends (confirmed) | Likely pfSense contract | Effect |
|---|---|---|---|---|
| **P0** | `vpn_openvpn.py:192,322,489` | data cipher under key `crypto` | field is `data_ciphers` / `data_ciphers_fallback`, a `many` array **(verify)** | cipher dropped → server uses default cipher |
| **P0** | `vpn_openvpn.py:188,318` (validated int `:167`) | `dh_length` as **int** | string enum (`"2048"`) **(verify)** | DH param dropped/rejected |
| **P0** | `vpn_wireguard.py:338` | peer interval under key `keepalive` | field is `persistentkeepalive` **(verify)** | keepalive never set |
| **P0** | `vpn_wireguard.py:334` | peer `port` as a **separate field** | port is embedded in `endpoint` as `host:port` **(verify)** | endpoint has no port |
| **P0** | `dhcp.py` (`update_dhcp_server_config`, `create_dhcp_static_mapping`) | `dns_server` as bare string → `dnsserver` | `dnsserver` is a `many` array **(verify)** | DNS server dropped/mis-coerced |
| **P0** | `dhcp.py` (`update_dhcp_server_config`) | `range_from`/`range_to` flat on the server object | pool range lives in a nested `range`/address-pool child **(verify)** | pool never updates |
| **P1** | `interfaces.py:115` | `subnet` (CIDR bits) as **int** | string choice (`"24"`) — same class as #13 **(verify)** | static interface subnet dropped |
| **P1** | `vpn_ipsec.py:108,137` | `authentication_method` vocabulary uses `cert` | enum is `pre_shared_key`/`rsasig`/`eap-*`; also **no `caref`/`certref` params** **(verify)** | cert-auth P1 can't be created |
| **P1** | `vpn_ipsec.py:650`, `vpn_advanced.py:70` | `dhgroup`, `encryption_algorithm_keylen` as **int** | string enums (`"14"`) **(verify)** | dropped |
| **P1** | `vpn_openvpn.py:834,910` | CSO associates via `server_id` | model uses `server_list` (`many`) **(verify)** | override applies globally, not per-server |
| **P1** | `certificates.py:115,238,450` | `keylen`, `lifetime` as **int** | commonly string choices **(verify)** | dropped |
| **P1** | `users.py:303,388` | group `member` = `List[int]` of "user IDs" | `Group.member` references **`uid`**, but search returns array-index `id` | wrong/no members |
| **P1** | `firewall.py:66` | `QueryFilter("disabled", disabled)` → stringifies to **`"True"`** (`models.py:42`) | boolean query value must be lowercase `"true"` | **disabled-rule search silently matches nothing** (high confidence) |
| **P2** | `vpn_advanced.py:36,243,…` | `QueryFilter("parent_id", <int>)` | sibling code uses `str(parent_id)` (`vpn_ipsec.py:616`) | inconsistent/ignored filter |
| **P2** | `dhcp.py:426` | `default_lease_time`/`max_lease_time` as int | historically string **(verify)** | possibly dropped |
| **P2** | `dns_resolver.py` (`update_dns_resolver_settings`) | omits `port`/`enablessl`; `forwarding`/`register_dhcp` names unverified | Unbound model often `regdhcp`/`regdhcpstatic` **(verify)** | wrong names dropped |

**Systemic fix (P1):** add a per-endpoint **allowed-field allowlist** (hand-authored, or fetched from the REST API model schema at startup) and emit a warning when a tool sends a key not in it. This converts an entire invisible bug class into a startup/test-time signal.

**Wire-layer strengths (done right):** `port`-as-string fix (`system_advanced.py:206`, #7); firewall-rule `interface` array vs NAT scalar; control params merged into JSON body with type coercion (`client.py:210-228`); Content-Type omitted on GET/bodyless-DELETE; DELETE routed through `request()` (#12); `protocol="any"`→`None`; WireGuard tunnel filter correctly uses `str(enabled).lower()` (`vpn_wireguard.py:52`) — the exact pattern `firewall.py:66` is missing.

---

## 4. Section B — Security & guardrails

| Sev | Finding | Reference |
|---|---|---|
| **P0** | **`manage_*` / `control_service` tools carry no guardrail decorator** → full bypass of rate-limit, sanitization, allowlist, audit. `control_service` can `stop dhcpd/unbound/sshd` with no throttle/audit. | `services.py:63`, `aliases.py:88`, `misc_services.py:136,418`, `pkg_haproxy.py:285,650`, `pkg_bind.py:294,524`, `vpn_wireguard.py:518`, `vpn_advanced.py:272` |
| **P0** | **Confirm gate is opt-in per tool, not enforced at registration.** A destructive tool that forgets `@guarded` ships un-gated. `manage_openvpn_cso` is `destructiveHint=True`, deletes, and hand-rolls its own confirm (skipping rate-limit/audit/allowlist/dry-run) — the pattern is already drifting. | `guardrails.py:687`; `vpn_openvpn.py:829,886` |
| **P1** | **Secrets can leak via echoed API error bodies.** On 4xx the full `response.text` is raised and returned as `{"error": ...}`; pfSense echoes offending field values, so `password`/`prv`/`radius_secret`/`ipsecpsk`/`ldap_bindpw` can surface in output/logs unredacted. | `client.py:271-301`; `users.py:127`, `certificates.py:143` |
| **P1** | **Risk classification is name/prefix-based and fragile.** A destructive tool misclassified below HIGH (e.g. a future `purge_*`/`flush_*`, or `manage_*` that deletes) **bypasses the confirm gate**. The "fixed 13 misclassifications" commit was whack-a-mole on the string table. | `guardrails.py:46-105` |
| **P1** | **Rate limiter is in-memory per-process.** Multiplied by N under any multi-worker HTTP deploy, shared by none, and reset on restart (a crash-loop evades limits). | `guardrails.py:308-372`; `main.py:177` |
| **P1** | **Config backup/rollback silently no-ops on failure.** The pre-change revision capture is wrapped in `except Exception: pass`; if it fails the destructive op proceeds with no rollback pointer and no warning — contradicting the "always backs up" claim. `restore_config_backup`'s own PATCH semantics are unverified (contradictory in-code comments). | `guardrails.py:730-771`; `diagnostics.py:331-335` |
| **P1** | **`CHANGE-ME` placeholder API key not rejected.** HTTP mode only rejects an *empty* `MCP_API_KEY`; a deploy left on the documented placeholder boots with a publicly-known key. | `.env.example:25`; `main.py:159-165` |
| **P2** | **Input "sanitization" is a naive denylist** (`;\s*\w`, `<script>`, …) for values that land as JSON, not in a shell/HTML sink → false sense of security + false positives on legit values (LDAP DNs, URLs, descriptions). The one real command sink (`/diagnostics/command_prompt`) is correctly hard-allowlisted instead. | `guardrails.py:491-516`; `client.py:973-997` |
| **P2** | **Secret-redaction key list is incomplete and exact-match.** Misses `radius_secret`, `ldap_bindpw`, `ipsecpsk`, `authorizedkeys` → logged in cleartext by the audit path. | `guardrails.py:243-246,673` |
| **P2** | **`export_*` tools bypass read-only safety.** `export_certificate_pkcs12` (private-key bundle, takes a passphrase) and `export_openvpn_client_config` are `readOnlyHint=True` and classified READ via the `export_` prefix → retained in `MCP_READ_ONLY` mode and skip rate-limit/audit, despite issuing POST. | `certificates.py:316`; `vpn_openvpn.py:1023`; `guardrails.py:84` |
| **P2** | **`Origin: null` / missing-Origin allowed.** Weakens DNS-rebinding protection; bearer auth is the real boundary (document it as such). | `middleware.py:50-55` |
| **P3** | Audit log marketed "immutable" but is a best-effort unlocked/unrotated file append; reversibility flag contradicts the "cannot be undone" impact text; `MCP_API_KEY` has no min-length/entropy check. | `guardrails.py:160,218,296-301`; `middleware.py:42` |

**Genuine strengths:** confirm gate is consistently applied to every `delete_*`/power tool (full grep, no misses) and fails safe (unknown → MEDIUM, not READ); the diagnostic shell sink is hard-allowlisted (the correct design); timing-safe token compare + fail-closed HTTP startup; positive validation for IP/port/alias/MAC/log-type is sound; request logging omits query strings and bodies; stale-ID `verify_descr` guard on firewall edits.

---

## 5. Section C — Core architecture & HTTP client

| Sev | Finding | Reference |
|---|---|---|
| **P0** | **All HTTP errors raised as bare `Exception`** carrying a multi-line string; callers substring-match to classify (`if "401" in str`). Makes correct error handling across 327 tools impossible. | `client.py:301`, `:1178-1188` |
| **P0** | **No retry/backoff anywhere** — a momentary TLS/keepalive blip or transient 502/503 fails the whole tool call. | `client.py:250-266` |
| **P0** | **429 / `Retry-After` not honored** (treated as a generic error; with no retry, legitimate throttling hard-fails). | `client.py:271-301` |
| **P1** | **Module-global singleton client** blocks multi-instance and is the central testability obstacle; preflight does a build/close/`reset` dance only to dodge the event-loop problem. | `server.py:45-111`; `main.py:113-136` |
| **P1** | **`self.version`/`version_map` is a dead abstraction** — stored, never read; implies multi-version support that doesn't exist (CE vs Plus divergence is unhandled). | `client.py:49`; `server.py:60-72` |
| **P1** | **JWT refresh has no lock and a hardcoded 1h expiry** (ignores the token's real `exp`; no 401-triggered refresh-and-retry). | `client.py:102-136` |
| **P1** | **No connection-pool limits** (`httpx` defaults) — concurrent calls can overwhelm pfSense's modest PHP-FPM workers. | `client.py:76-80` |
| **P1** | **Large responses fully buffered** via `response.json()`; no size guard (the log-OOM workaround addresses only read-timeout on log endpoints). | `client.py:305`, `:582-611` |
| **P2** | Read-only mode mutates FastMCP private internals (`_tool_manager._tools`) — a framework upgrade can silently break a security feature; gate at registration instead. Control-param string→native round-trip is tech debt; `_ensure_client` leaks the prior client on loop change; `follow_link` HATEOAS rewriting is brittle. | `main.py:58-61`; `client.py:59-81,210-228,1153-1161` |
| **P3** | Version mismatch (`__init__.py:6` says `5.0.0` vs `server.py:27` `1.0.0`); mixed `%`/f-string logging; no structured/correlation logging; naive-local `datetime.now()` for JWT expiry. | as cited |

**Strengths:** API-quirk handling is excellent and well-commented; the per-request read-timeout uses `httpx.Timeout` precisely; stale-ID guards address pfSense's non-persistent array-index IDs; sensible security defaults throughout.

---

## 6. Section D — Tool coverage & CRUD gaps

**CRUD holes (create/read exist; update and/or delete missing):**
- Interface **bridges** and **groups** — create+search only, no update/delete (`interfaces.py:530,629`). **P1**
- DNS **forwarder settings** — get but no update (can't enable/disable dnsmasq, set port) (`dns_forwarder.py`). **P1**
- IPsec **phase1 encryption** — create/search/delete, no update (`vpn_ipsec.py:647`). **P1**
- DNS resolver host-override **aliases** asymmetric vs forwarder; access-list `networks` immutable post-create; DHCP static-mapping update drops `domain`/`gateway`/`dnsserver`; DHCP static-mapping delete lacks a stale-ID guard. **P2**

**Consistency issues:** the two `export_*` annotation/guardrail bypasses (§4); `manage_*` mutating tools missing decorators (§4); client-side `search_term` filtering applied *after* server-side pagination in many `search_*` tools (matches beyond page 1 silently missed; `count` vs pagination semantics diverge) — `nat_outbound.py:53`, `system_settings.py:177`, `virtual_ips.py:60`, etc. **P2**

**Duplication/dead:** three overlapping OpenVPN status reads (`vpn_openvpn.py:986`, `vpn_advanced.py:370,388`); dead `async_mode` control flag (`models.py:84`). **P3**

---

## 7. Section E — New capability opportunities (feature roadmap)

Not yet exposed, ranked by typical demand — candidate headline features for the next release:

1. **IDS/IPS — Snort & Suricata** (alerts, rule management, blocked hosts). Highest-demand missing package.
2. **pfBlockerNG** (DNSBL / IP feeds, allow/block lists).
3. **Captive Portal** (zones, vouchers, MAC management).
4. **GRE/GIF tunnels** and **LAGG** interfaces (only VLAN/bridge/group covered today).
5. **SNMP, UPnP/NAT-PMP, IGMP proxy, wireless/hostapd, NTP server status.**
6. **DHCPv6 / Router Advertisements**, **DDNS clients**, **Certificate CSR** workflow, **CA export**.
7. Complete **IPsec Phase 2** detail (lifetime/PFS) with an update path; fix **OpenVPN CSC/CSO** (`server_list`).

(HAProxy / ACME / BIND / FreeRADIUS are already covered — keep them as differentiators.)

---

## 8. Section F — Testing, CI, packaging, ops

| Sev | Finding |
|---|---|
| **P0** | Top-level package literally named **`src`** → **PyPI-publish blocker** (site-packages namespace collision). Internal imports are all relative, so renaming to `pfsense_mcp_server` is mechanical/low-risk. Docker is unaffected (it `COPY`s `src/` and runs `python -m src.main`). |
| **P0** | **No SECURITY.md / vuln-disclosure policy** on a firewall-management tool. |
| **P1** | Real tool coverage **~17%** — 9 of 35 modules tested; **270 of 327 tools never exercised**. The `mock_client` pattern makes 2-3 round-trip tests per module cheap. |
| **P1** | **JWT acquisition/refresh untested and un-mockable** via the current `_make_request` seam (it calls `self.client.post` directly); **no integration/contract test** against a real or recorded pfSense. |
| **P1** | CI: single Python version (no 3.12/3.13 matrix); **no security scanning** (pip-audit/bandit/Dependabot); **no release/publish automation** (PyPI, Docker image, tag-triggered release). |
| **P1** | pyproject missing PyPI metadata (`authors`, `classifiers`, `keywords`, `urls`); secrets only via plain env (no `*_FILE`/Docker secrets); streamable-http production story thin (in-memory guardrail state unsafe across replicas; no TLS/reverse-proxy guidance). |
| **P2** | No coverage gate (`--cov` reported, never enforced); transport/middleware/guardrail edge cases untested; dependency divergence (httpx unpinned in pyproject vs bounded in requirements.txt) + no lockfile; version duplicated across 4 files; no multi-arch image; `.dockerignore` misses `build/`/`dist/`/`*.egg-info/`/`.venv/`. |
| **P3** | No issue/PR templates, no CODE_OF_CONDUCT, no ARCHITECTURE.md/threat model, no RELEASING.md, CI only on main (no weekly drift run). |

**Strengths:** conftest forces dummy env (no real-cred leakage) and resets rate limiters between tests; the transport seam *is* partially tested (Content-Type gating, DELETE-with-body, 4xx raising); Docker hardening is strong (`no-new-privileges`, read-only FS, `cap_drop: ALL`, healthcheck); HTTP fails closed on missing key; docs are above average.

---

## 9. Consolidated must-fix list

**P0 — gate the release**
1. Wire-format P0s: OpenVPN `crypto`→`data_ciphers` + `dh_length` int→str; WireGuard `keepalive`→`persistentkeepalive` + peer `port`→`endpoint`; DHCP `dnsserver` scalar→array + `range_*` nesting. *(verify each against the model first.)*
2. Add the systemic **field-name validation layer** so the next #13 surfaces at startup/test time.
3. Guardrails: add decorators to all `manage_*`/`control_service` tools **and** enforce the confirm gate at registration (assert every HIGH/CRITICAL or `destructiveHint=True` tool is `@guarded`).
4. Redact secrets in API **error** bodies (`client.py` error path).
5. Rename the `src` package → `pfsense_mcp_server` (PyPI blocker); add **SECURITY.md**; reject the `CHANGE-ME` placeholder key.

**P1 — credible major release**
6. Typed exception hierarchy + retry/backoff + 429/`Retry-After` (`client.py`).
7. Decouple the global singleton → client factory/registry (prereq for multi-instance + clean tests).
8. Make `version` real (capability/endpoint profiles) or remove it.
9. JWT lock + real `exp` + 401-retry; connection-pool limits; large-response guard.
10. Fix name-based risk classification (drive from `destructiveHint`); fix `export_*` bypass; widen secret-redaction key list; surface rollback-capture failure and verify `restore_config_backup`.
11. Raise tool coverage from ~17% (target ≥60%); add JWT + integration/contract tests; CI matrix + pip-audit/bandit + Dependabot + release automation; pyproject PyPI metadata + lockfile.

---

## 10. Proposed release plan

A single "big release" trying to do all of the above will stall. Suggested phasing (semver-aligned):

- **v1.1.0 — "Correctness" (fast follow, weeks):** all wire-format P0/P1 fixes (§3) + the field-name validation layer + the `firewall.py:66` disabled-filter fix + CRUD-hole fills (bridges/groups update-delete, DNS forwarder update, IPsec P1 update). Pure correctness; high user value; low architectural risk. Each wire-format fix ships with a test asserting the exact key/type sent.

- **v1.2.0 — "Trustworthy safety":** centralize the confirm gate at registration, decorate/clean the `manage_*`/`control_service` gap, redact error-body secrets, widen redaction, drive risk from annotations, fix `export_*`, make rollback honest, reject the placeholder key, add SECURITY.md + threat model. Re-frame the safety docs to match reality.

- **v2.0.0 — "Production platform" (breaking):** rename package to `pfsense_mcp_server` + PyPI publish; typed-exception/retry/429 client rewrite; client factory/registry + **multi-instance** support; real version profiles; JWT/pool/large-response hardening; structured logging + observability; CI matrix + security scanning + release/Docker automation; coverage ≥60% + integration/contract suite. The package rename and error-contract change are the breaking pieces that justify the major bump.

- **vNext — "Coverage expansion":** Snort/Suricata, pfBlockerNG, Captive Portal, GRE/GIF/LAGG, and the rest of §7, each on the now-validated wire-format foundation.

**Sequencing rationale:** correctness before capability (don't build new tools on an unvalidated wire layer); safety credibility before marketing safety; the breaking architectural work batched into one major bump so users absorb the package rename and error-contract change once.

---

*This is a static audit; wire-format "(verify)" items must be confirmed against the installed pfSense REST API model schema before code changes. No files other than this report were created or modified.*
