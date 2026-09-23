"""Every place that states the release version must agree.

The version lives in four files (pyproject, server.VERSION — what MCP
serverInfo reports — the Dockerfile image label, and the Makefile), and
nothing tied them together, so a release could ship with serverInfo saying
one version and the package another.
"""
import re
import tomllib
from pathlib import Path

from src.server import VERSION

ROOT = Path(__file__).resolve().parent.parent


def _match(path: str, pattern: str) -> str:
    m = re.search(pattern, (ROOT / path).read_text(), re.MULTILINE)
    assert m, f"no version found in {path}"
    return m.group(1)


def test_versions_agree():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert VERSION == pyproject
    assert _match("Dockerfile", r"^ARG VERSION=(\S+)") == pyproject
    assert _match("Makefile", r"^VERSION \?= (\S+)") == pyproject


def test_changelog_has_section_for_version():
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert re.search(rf"^## \[{re.escape(VERSION)}\]", changelog, re.MULTILINE), (
        f"CHANGELOG.md has no '## [{VERSION}]' section"
    )
