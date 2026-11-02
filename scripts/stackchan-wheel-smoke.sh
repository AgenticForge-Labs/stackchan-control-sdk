#!/usr/bin/env bash
# Build and exercise the SDK wheel without hardware or network access.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SMOKE_DIR="$(mktemp -d)"
trap 'rm -rf "$SMOKE_DIR"' EXIT

uv build --offline --wheel --out-dir "$SMOKE_DIR/wheels" "$ROOT"
uv venv --offline --python 3.12 "$SMOKE_DIR/venv"
VENV_PY="$SMOKE_DIR/venv/bin/python"
VENV_BIN="$SMOKE_DIR/venv/bin"
uv pip install --offline --python "$VENV_PY" --no-deps "$SMOKE_DIR"/wheels/*.whl

"$VENV_BIN/stackchan" --help >/dev/null
"$VENV_BIN/stackchan-probe" --help >/dev/null

"$VENV_PY" - <<'PY'
import contextlib
import io
import json
from importlib.metadata import distribution

from stackchan_control import cli
from stackchan_control.external_protocol import ExternalEvent


metadata = distribution("stackchan-control").metadata
requirements = metadata.get_all("Requires-Dist") or []
assert not any("forge-puppeteer" in item.lower() or "mcp" in item.lower() for item in requirements)


class FakeClient:
    def __init__(self):
        self.calls = []
        self.closed = False

    def submit(self, method, params=None):
        self.calls.append((method, params))
        return str(len(self.calls))

    def wait(self, ident, *, timeout):
        method = self.calls[int(ident) - 1][0]
        if method == "system.capabilities":
            result = {
                "protocol_version": "1.0",
                "capabilities": ["system.state", "motion.update.position_only"],
            }
        elif method == "system.state":
            result = {"native_angle_limits_tenths": {"yaw": [-500, 500], "pitch": [30, 870]}}
        else:
            result = {}
        return (ExternalEvent("completed", ident, result=result),)

    def close(self):
        self.closed = True


client = FakeClient()
cli.RoutedSerialClient.open = lambda _port: client
for arguments in (
    ["--port", "fake", "discover"],
    ["--port", "fake", "state"],
    ["--port", "fake", "head", "--yaw", "10", "--speed", "20"],
):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        assert cli.main(arguments) == 0
    assert json.loads(stdout.getvalue())["ok"] is True

assert [method for method, _ in client.calls] == [
    "system.capabilities",
    "system.capabilities", "system.state",
    "system.capabilities", "system.capabilities", "system.state", "motion.update",
]
assert client.calls[-1][1] == {"yawServo": {"angle": 10, "speed": 20}}
assert client.closed
print("installed StackChan wheel CLI smoke passed")
PY
