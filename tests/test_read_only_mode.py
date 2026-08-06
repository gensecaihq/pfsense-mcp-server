"""Boot tests for MCP_READ_ONLY mode.

Read-only mode filters the registered tool set at import time in ``src.main``.
That reduction is a module-level side effect, so it can only be exercised
faithfully in a fresh interpreter — these tests spawn subprocesses.

Regression context: the pre-FastMCP-3 code reached into the private
``mcp._tool_manager._tools``. FastMCP 3 removed ``_tool_manager``, so
``MCP_READ_ONLY=true`` raised ``AttributeError`` at import and the documented
least-privilege mode would not start at all. The first test below fails if that
recurs; the second asserts the reduction actually keeps read tools and drops
destructive ones.
"""

import subprocess
import sys

# Env that lets src.main import without a real pfSense (matches conftest values).
_BASE_ENV = {
    "PFSENSE_URL": "https://192.0.2.1",
    "PFSENSE_API_KEY": "test-key",
    "AUTH_METHOD": "api_key",
    "VERIFY_SSL": "false",
}


def _run(code: str, read_only: bool):
    import os

    env = dict(os.environ)
    env.update(_BASE_ENV)
    env["MCP_READ_ONLY"] = "true" if read_only else "false"
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )


def test_read_only_mode_imports_without_crashing():
    """MCP_READ_ONLY=true must not raise at import (the FastMCP-3 regression)."""
    result = _run("import src.main", read_only=True)
    assert result.returncode == 0, (
        "importing src.main with MCP_READ_ONLY=true failed:\n" + result.stderr
    )
    assert "AttributeError" not in result.stderr


def test_read_only_mode_keeps_read_tools_and_drops_destructive():
    """The reduction keeps read-level tools and removes destructive ones."""
    code = (
        "import asyncio, src.main\n"
        "from src.server import mcp\n"
        "names = {t.name for t in asyncio.run(mcp.local_provider.list_tools())}\n"
        "assert 'search_firewall_rules' in names, 'read tool missing'\n"
        "assert 'delete_firewall_rule' not in names, 'destructive tool survived'\n"
        "print(len(names))\n"
    )
    result = _run(code, read_only=True)
    assert result.returncode == 0, result.stderr
    remaining = int(result.stdout.strip().splitlines()[-1])
    # Read-only exposes the read subset only: fewer than the full set, non-empty.
    assert 0 < remaining < 327


def test_full_mode_registers_all_tools():
    """Without read-only, the full tool set is registered (sanity baseline)."""
    code = (
        "import asyncio, src.main\n"
        "from src.server import mcp\n"
        "print(len(asyncio.run(mcp.local_provider.list_tools())))\n"
    )
    result = _run(code, read_only=False)
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip().splitlines()[-1]) == 327
