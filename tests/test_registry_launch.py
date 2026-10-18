"""
The MCP registry entry starts the server (issue #18).

``server.json`` declared no ``packageArguments``, so ``uvx sdcgovernance`` ran
``main()`` with no arguments, which printed the CLI help and exited. These
tests start the console script's entry point the way a registry client, a
hand-written configuration and the pre-4.2.5 configuration do, and check that
``server.json`` names the released version.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import sdcgovernance
from sdcgovernance.mcp_server import SERVER_VERSION

ROOT = Path(__file__).resolve().parents[1]
SERVER_JSON = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))

INITIALIZE = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}


def _launch(args):
    proc = subprocess.run(
        [sys.executable, "-m", "sdcgovernance.mcp_server", *args],
        input=json.dumps(INITIALIZE) + "\n",
        capture_output=True, text=True, timeout=60,
    )
    return proc


def _registry_args():
    package = SERVER_JSON["packages"][0]
    return [a["value"] for a in package.get("packageArguments", []) if a["type"] == "positional"]


@pytest.mark.parametrize("args", [
    pytest.param([], id="bare, what a registry client without packageArguments runs"),
    pytest.param(_registry_args(), id="server.json packageArguments"),
    pytest.param(["mcp"], id="mcp"),
    pytest.param(["serve", "--mcp"], id="serve --mcp (pre-4.2.5 configurations)"),
])
def test_each_launch_spelling_answers_initialize(args):
    proc = _launch(args)
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert lines, f"no JSON-RPC response; stdout was help text?\n{proc.stdout}"
    response = json.loads(lines[0])
    assert response["id"] == 1
    assert response["result"]["serverInfo"]["name"] == "sdcgovernance"
    assert response["result"]["serverInfo"]["version"] == SERVER_VERSION
    assert "usage:" not in proc.stdout


def test_serve_without_mcp_still_prints_help():
    proc = _launch(["serve"])
    assert proc.returncode == 0
    assert "usage:" in proc.stdout


def test_server_json_declares_the_mcp_launch():
    package = SERVER_JSON["packages"][0]
    assert package["identifier"] == "sdcgovernance"
    assert package["runtimeHint"] == "uvx"
    assert _registry_args() == ["mcp"]


def test_server_json_names_the_released_version():
    # A regex, not tomllib: the test matrix includes Python 3.10.
    pyproject = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    assert SERVER_JSON["version"] == pyproject
    assert SERVER_JSON["packages"][0]["version"] == pyproject
    assert sdcgovernance.__version__ == pyproject
    assert SERVER_VERSION == pyproject
