# Contributing

Thanks for helping improve the pfSense MCP Server. Real-world testing across
diverse pfSense environments is especially valuable.

## Development setup

Requires **Python 3.11+** (`fastmcp` needs ≥3.10 and the package declares
`requires-python = ">=3.11"`).

```bash
git clone https://github.com/gensecaihq/pfsense-mcp-server.git
cd pfsense-mcp-server

python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"        # installs runtime + pytest, ruff
```

## Before you open a PR

Run the full suite and the linter — CI runs both and must pass:

```bash
pytest -v                      # 483 tests
pytest --cov=src               # with coverage (CI gate: >=40%)
ruff check src/ tests/         # lint (must be clean)
```

If your change touches transports, auth, startup, or tool registration, also
run the protocol-level E2E suite that CI runs (`mcp-inspector-e2e`) — it
drives the server over the real MCP wire protocol with the MCP Inspector CLI
and needs `node`/`npx` and `jq`, but no pfSense instance:

```bash
make test-e2e                  # or: ./scripts/inspector_smoke.sh
```

Add or update tests for any behavior you change. Tool tests live under
`tests/tools/`; they patch `_make_request` via the `mock_client` /
`mock_make_request` fixtures in `tests/conftest.py` and assert on the JSON body
the tool sends — match that pattern.

## Guidelines

- **Mirror the pfSense REST API field names verbatim, and add a contract test.**
  A whole class of past bugs was silent field drops — a tool sending a key/type
  the API model doesn't recognize, which pfSense drops on PATCH or 400s on POST.
  The wire contract in `tests/contract/` (distilled from the upstream OpenAPI
  spec, see `scripts/generate_contract.py`) catches these: use
  `assert_payload_valid()` to check your tool's payload against the real
  v2.10.0 model. See `ARCHITECTURE.md` and the existing `tests/contract/test_*`.
- **Respect the guardrail model.** Every non-read tool must carry a guardrail
  decorator — `@guarded` for destructive tools (which also take `confirm`/
  `dry_run`) or `@rate_limited` for other mutating tools — and the right
  `ToolAnnotations`. This is enforced at import by
  `tests/test_guardrail_coverage.py`, so an undecorated mutating tool fails CI.
  Risk classification lives in `src/guardrails.py`.
- **Don't log secrets.** Sensitive parameters are redacted centrally; don't add
  code paths that print raw request bodies or credentials.
- Keep changes focused and match the style of the surrounding code.

## Submitting

1. Fork and create a feature branch.
2. Make your change with tests; ensure `pytest` and `ruff check` pass.
3. Open a PR describing the problem and the fix. If it addresses an issue,
   reference it (e.g. `Closes #NN`).

## Ideas

Integration tests against real pfSense, additional package support (Snort,
Suricata), an Ollama local-LLM bridge, and multi-instance management are all
welcome.
