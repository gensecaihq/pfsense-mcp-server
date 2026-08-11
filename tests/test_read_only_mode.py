"""Boot tests for MCP_READ_ONLY mode.

Read-only mode filters the registered tool set in ``main()`` via
``apply_read_only_filter()``. Because that mutates the process-global ``mcp``
registry, the tests run it in fresh subprocesses so they can't pollute one
another or the rest of the suite.

Regression context, two bugs this guards against:
- The pre-FastMCP-3 code reached into the private ``mcp._tool_manager._tools``.
  FastMCP 3 removed ``_tool_manager``, so read-only mode raised ``AttributeError``.
- The replacement first ran the reduction (an ``asyncio.run``) at *import* time;
  on Python 3.11 that can deadlock against the import lock. The reduction now
  runs from ``main()`` after imports complete. These tests exercise both the
  filter result and a plain ``import src.main`` staying trivial.
"""

import os
import subprocess
import sys

# Env that lets src.main import without a real pfSense (matches conftest values).
_BASE_ENV = {
    "PFSENSE_URL": "https://192.0.2.1",
    "PFSENSE_API_KEY": "test-key",
    "AUTH_METHOD": "api_key",
    "VERIFY_SSL": "false",
}

# A generous per-subprocess cap. Importing the app registers 327 tools and runs
# the read-only reduction; that takes ~1s. A hang means a real regression, and
# the timeout turns it into a fast, diagnostic failure instead of a stuck CI job.
_SUBPROC_TIMEOUT = 120


def _clean_env(read_only: bool) -> dict:
    """Minimal env for a hermetic child interpreter.

    Deliberately drops pytest-cov's subprocess-coverage injection
    (``COVERAGE_PROCESS_START`` / ``COV_CORE_*``): a boot test must exercise a
    plain interpreter, not one that auto-starts coverage via a ``.pth`` hook —
    that hook is the one thing that differs between a local run and CI's
    ``pytest --cov`` run, and it must not influence startup behavior.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if not (k.startswith("COV_CORE") or k == "COVERAGE_PROCESS_START")
    }
    env.update(_BASE_ENV)
    env["MCP_READ_ONLY"] = "true" if read_only else "false"
    return env


def _run(code: str, read_only: bool):
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=_clean_env(read_only),
        stdin=subprocess.DEVNULL,
        timeout=_SUBPROC_TIMEOUT,
    )


def test_import_is_trivial_in_read_only_mode():
    """Importing src.main must not crash or hang even with MCP_READ_ONLY=true.

    Guards the FastMCP-3 AttributeError and the import-time asyncio deadlock:
    import now has no read-only side effect at all.
    """
    result = _run("import src.main", read_only=True)
    assert result.returncode == 0, (
        "importing src.main with MCP_READ_ONLY=true failed:\n" + result.stderr
    )
    assert "AttributeError" not in result.stderr


def test_filter_keeps_read_tools_and_drops_destructive():
    """apply_read_only_filter() keeps read-level tools and removes the rest."""
    code = (
        "import asyncio, src.main\n"
        "removed = src.main.apply_read_only_filter()\n"
        "from src.server import mcp\n"
        "names = {t.name for t in asyncio.run(mcp.local_provider.list_tools())}\n"
        "assert 'search_firewall_rules' in names, 'read tool missing'\n"
        "assert 'delete_firewall_rule' not in names, 'destructive tool survived'\n"
        "print(removed, len(names))\n"
    )
    result = _run(code, read_only=True)
    assert result.returncode == 0, result.stderr
    removed, remaining = (int(x) for x in result.stdout.strip().splitlines()[-1].split())
    assert removed > 0
    # Read-only exposes the read subset only: fewer than the full set, non-empty.
    assert 0 < remaining < 333


def test_filter_is_noop_and_full_set_registered_without_read_only():
    """Without read-only, the filter removes nothing and all tools remain."""
    code = (
        "import asyncio, src.main\n"
        "removed = src.main.apply_read_only_filter()\n"
        "from src.server import mcp\n"
        "total = len(asyncio.run(mcp.local_provider.list_tools()))\n"
        "print(removed, total)\n"
    )
    result = _run(code, read_only=False)
    assert result.returncode == 0, result.stderr
    removed, total = (int(x) for x in result.stdout.strip().splitlines()[-1].split())
    assert removed == 0
    assert total == 333
