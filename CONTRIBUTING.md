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
pytest -v                      # 323 tests
pytest --cov=src               # with coverage
ruff check src/ tests/         # lint (must be clean)
```

Add or update tests for any behavior you change. Tool tests live under
`tests/tools/`; they patch `_make_request` via the `mock_client` /
`mock_make_request` fixtures in `tests/conftest.py` and assert on the JSON body
the tool sends — match that pattern.

## Guidelines

- **Mirror the pfSense REST API field names verbatim.** Several past bugs (#7,
  #13) were silent field drops caused by a tool using a different key than the
  API expects. When in doubt, check the API's OpenAPI schema / a live response.
- **Respect the guardrail model.** New destructive tools must take `confirm`,
  carry the right `ToolAnnotations`, and (for create/update) the `@rate_limited`
  decorator. Risk classification lives in `src/guardrails.py`.
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
