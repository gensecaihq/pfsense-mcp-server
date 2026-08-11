# Security Policy

The pfSense MCP Server issues privileged changes to firewall, VPN, and network
configuration through the pfSense REST API. Security reports are taken
seriously.

## Reporting a Vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately via GitHub's [private vulnerability
reporting](https://github.com/gensecaihq/pfsense-mcp-server/security/advisories/new)
("Report a vulnerability" on the repository's **Security** tab). If that is
unavailable, contact the maintainers through the organization's security
contact listed on the GitHub organization profile.

Please include:

- affected version / commit,
- transport in use (`stdio` or `streamable-http`) and deployment shape,
- a description and, where possible, a minimal reproduction,
- the impact you observed.

You can expect an acknowledgement within a few business days and a coordinated
disclosure timeline once the report is triaged.

## Scope

In scope: the MCP server code in this repository — the guardrail system,
authentication and transport handling, credential/secret handling, and the tool
wire-format layer.

Out of scope: vulnerabilities in pfSense itself or in the
[pfSense-pkg-RESTAPI](https://github.com/pfrest/pfSense-pkg-RESTAPI) package
(report those to their respective projects), and misconfigurations of a
deployment that ignore the hardening guidance below.

## Deployment hardening

- **stdio transport** (default) is the intended mode for a single trusted
  operator; it has no network listener.
- **streamable-http transport** requires `MCP_API_KEY`; the server refuses to
  start with an unset, placeholder, or too-short token. Bind to `127.0.0.1`
  (the default) and terminate TLS at a reverse proxy. Set `MCP_ALLOWED_ORIGINS`
  in production.
- Give the pfSense API key the least privilege the tools need.
- Prefer `MCP_READ_ONLY=true` and/or `MCP_ALLOWED_TOOLS` to reduce the exposed
  surface where full write access is not required.
- Keep the pfSense REST API package updated (see the compatibility matrix in
  the README; releases before pkg-RESTAPI v2.10.0 carry known advisories —
  GHSA-w3w4-mvcc-vmgr, fixed in v2.10.0, and GHSA-8q8g-9f77-8g8g, fixed in
  v2.9.0).

## Supported versions

Security fixes target the latest release on the default branch.
