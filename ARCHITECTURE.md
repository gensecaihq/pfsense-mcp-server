# Architecture

How the pfSense MCP Server is put together, for contributors and reviewers.

## Overview

The server exposes 327 tools over the [Model Context Protocol](https://modelcontextprotocol.io)
that translate natural-language intent into calls against the
[pfSense REST API v2](https://github.com/pfrest/pfSense-pkg-RESTAPI). It is a
single-process, single-firewall server driven by a trusted operator; it holds no
per-request session state.

```
MCP client (Claude Desktop / Code / …)
        │  stdio  or  Streamable HTTP
        ▼
  ┌───────────────────────────────────────────────┐
  │ FastMCP server (src/server.py)                 │
  │   • 327 @mcp.tool functions (src/tools/*.py)   │
  │   • ToolAnnotations (read/destructive hints)   │
  └───────────────┬───────────────────────────────┘
                  │ each tool calls the API client
                  ▼
  ┌───────────────────────────────────────────────┐
  │ guardrails (src/guardrails.py)                 │
  │   classify → allowlist → sanitize → rate-limit │
  │   → confirm/dry-run → backup → execute → audit │
  └───────────────┬───────────────────────────────┘
                  ▼
  ┌───────────────────────────────────────────────┐
  │ EnhancedPfSenseAPIClient (src/client.py)       │
  │   auth, query/body building, retry/backoff,    │
  │   429 handling, connection pooling, redaction  │
  └───────────────┬───────────────────────────────┘
                  ▼  HTTPS /api/v2/...
            pfSense REST API v2 (pkg-RESTAPI v2.10.0)
```

## Modules

| File | Responsibility |
|---|---|
| `src/main.py` | CLI/entry point; transport selection (stdio / streamable-http); `MCP_READ_ONLY` tool filtering; `MCP_API_KEY` validation. |
| `src/server.py` | The `FastMCP` instance and the lazily-constructed global API client; `VERSION` (single source of truth). |
| `src/tools/*.py` | 34 modules of `@mcp.tool` functions, grouped by pfSense subsystem. Each maps tool arguments to the REST API wire format. |
| `src/guardrails.py` | Risk classification, the `@guarded` / `@rate_limited` decorators, input screening, rate limiting, audit logging, secret redaction, rollback capture. |
| `src/client.py` | HTTP client: auth headers (API key / basic / JWT), query + control-param assembly, retry/backoff, connection pooling, and typed CRUD helpers. |
| `src/middleware.py` | ASGI bearer-token + Origin validation for HTTP transport, plus the unauthenticated `/health` probe. |
| `src/helpers.py` | Positive input validation (IP/port/MAC/CIDR/FQDN), pagination, sanitization, sort helpers. |
| `src/models.py` | `QueryFilter`, `SortOptions`, `PaginationOptions`, `ControlParameters`, and the `PfSenseVersion` enum. |

## Request lifecycle

1. A tool receives typed arguments and builds the REST payload with the exact
   upstream field names/types.
2. If decorated, the guardrail wrapper runs: allowlist → sanitize → rate-limit →
   (for `@guarded`) confirm/dry-run gate → capture a pre-change config revision
   for HIGH/CRITICAL ops.
3. The tool calls a `client.crud_*` / `_make_request` helper.
4. The client attaches auth, merges control params into the JSON body (pfSense
   reads `apply`/`placement`/… from the body, not the query string), and sends
   the request — retrying transient failures (connection errors, `429`/`503`;
   read-timeouts and `502`/`504` for idempotent GETs only) with capped
   exponential backoff. Writes are never retried on an ambiguous response.
5. On `>= 400`, the error body is redacted and surfaced; on success the JSON is
   returned. `@guarded` tools attach a `config_backup` block (or a
   `config_backup_warning` if no rollback point could be captured) and an audit
   entry with redacted parameters.

## Guardrails

Risk is classified by tool-name prefix in `src/guardrails.py` (READ / LOW /
MEDIUM / HIGH / CRITICAL). Two decorators enforce it:

- `@guarded` — HIGH/CRITICAL destructive tools; requires `confirm=True`,
  supports `dry_run`, captures a rollback point, and audits.
- `@rate_limited` — other mutating tools; rate-limits, sanitizes, allowlist-
  checks, and audits without requiring confirmation.

Coverage is enforced at import by `tests/test_guardrail_coverage.py`: every
non-READ tool must carry one of these decorators (they set a `_guardrail`
marker), and every HIGH/CRITICAL tool must be `@guarded`. A forgotten decorator
is a failing test, not a silent hole.

`MCP_READ_ONLY=true` removes every non-READ tool at startup; `MCP_ALLOWED_TOOLS`
restricts to a named allowlist.

## Wire-contract test layer

pfSense's REST framework **silently ignores unknown request keys** and
**strictly type-checks known ones**, so a misnamed or mistyped field is either a
no-op that reports success (PATCH) or a hard 400 (POST) — invisible to a mocked
unit test. To make that failure mode visible:

- `scripts/generate_contract.py` distills the upstream OpenAPI spec (a
  pkg-RESTAPI release asset) into a slim, vendored contract
  (`tests/contract/contract-v2.10.0.json`): valid field names, JSON types, enum
  choices, and create-required fields per endpoint.
- `tests/contract/schema.py` exposes `assert_payload_valid(mock)` which captures
  a tool's actual `_make_request` payload and checks it against the contract.

Regenerate for a new pkg-RESTAPI version:

```bash
gh release download <tag> --repo pfrest/pfSense-pkg-RESTAPI --pattern openapi.json
python scripts/generate_contract.py openapi.json tests/contract/contract-<ver>.json --version <ver>
```

## Version compatibility

`PfSenseVersion` (`src/models.py`) enumerates supported releases; the value is
informational (it does not gate behavior today). The wire layer targets
pkg-RESTAPI **v2.10.0**. See the README compatibility matrix; legacy names such as
the historically-mislabeled `CE_26_03` remain accepted as enum aliases.

## MCP protocol

The server speaks MCP **2025-11-25** (via FastMCP 3.4.x) and negotiates down per
connection. It uses none of the features the 2026-07-28 revision deprecates
(Roots, Sampling, MCP Logging) and holds no session state, so it already passes
its suite on the FastMCP 4 beta (a non-blocking CI job) — adopting the
sessionless protocol will be a dependency-pin change.

## Known limitations

Single global API client (no multi-instance yet); errors are string-typed rather
than a typed hierarchy; the package is still named `src` (PyPI rename pending).
These and other items are tracked in `RELEASE_AUDIT.md`.
