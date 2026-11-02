# Public execution generation and STOP fencing

**Status:** Implemented on the SDK `agent/public-execution-generation-contract`
branch. This is an **SDK-owned native API**, not an MCP endpoint or a safety-rated
STOP mechanism. It is independently useful with Python/CLI and with Forge
Puppeteer's optional robot MCP adapter.

## Why

A caller may query live firmware state, validate a bounded action, or resolve
a pinned native asset before dispatching it. A STOP could occur during this
preparation. The caller needs one immutable token that the SDK checks again
at the **last host-side command-submission boundary**. The SDK already tracked
`_stop_generation`; this change makes its safe use public without creating
another owner or replacing SDK admission rules.

## API

```python
from stackchan_control import (
    AvatarUpdate, ExecutionState, ExternalControl, FeatureUpdate,
    NeoHexFrame, play_asset,
)

# Explicitly construct ExternalControl using an operator-opened
# RoutedSerialClient. No device is opened by importing the package.
state: ExecutionState = robot.execution_state()
# ... optional independent reasoning or capability discovery ...
robot.update_face(
    AvatarUpdate(mouth=FeatureUpdate(size=8)),
    expected_generation=state.generation,
)
robot.update_neohex(
    NeoHexFrame.solid("#000000", brightness=0),
    expected_generation=state.generation,
)
# Existing asset loader validates the revision and all typed steps.
play_asset(
    robot, asset,
    expected_revision=asset.revision,
    expected_generation=state.generation,
)
```

`execution_state()` returns a frozen `ExecutionState(generation: int)`.
It raises `RoutedSerialError` while STOP is pending or failed/unconfirmed.
Generation values are **local to the current ExternalControl instance**; they
are not persistent device identities, physical safety grants, firmware leases,
or reusable credentials. Do not reuse a token after closing/reopening the
serial client or after uncertain host/device disconnect. Do not infer motion
success or servo settling from this snapshot.

| Method | New optional keyword |
| --- | --- |
| `move_head` | `expected_generation` |
| `update_face` | `expected_generation` |
| `update_lights` | `expected_generation` |
| `update_neohex` | `expected_generation` |
| `play_asset` | `expected_generation` (in addition to mandatory `expected_revision`) |

Without an explicit token, existing manual Python callers retain the
current behavior: the SDK captures the current generation for each new
operation. For agent/workflow calls that prepare an action asynchronously,
**always** provide the previously observed generation to avoid dispatch
after an intervening STOP.

For now, legacy private `_generation` keyword arguments on the three
existing native methods remain accepted solely so installed clients and
the open Puppeteer StackChan PR do not break during migration. Supplying
both old and new keywords is an error. The future Puppeteer adapter
should use the public `execution_state()` and
`expected_generation=` arguments once this SDK change is accepted.

## Deterministic behavior

1. `stop()` increments the generation and sets the old STOP event under
   the SDK's native motion lock before it issues `system.stop`.
2. Each update checks the supplied token against the same lock immediately
   before `RoutedSerialClient.submit()`. A stale token refuses the write.
3. `move_head()` additionally retains its existing motion preflight
   lock, firmware capability/state limits and in-flight motion fence.
4. `play_asset()` checks both immutable asset revision and the
   supplied generation before the first step; each step carries the same
   generation through the native SDK calls. A STOP also interrupts timed
   waits. Replay never retries failed steps automatically.
5. `update_neohex()` uses the existing per-device NeoHEX lock plus
   generation-checked native submission. `sustain_neohex()` already
   captures one generation throughout its refresh loop; its cleanup
   and watchdog behavior are unchanged.
6. A partial serial write, timeout or connection loss is an **unknown
   outcome**, not approval to retry; the routed serial client never
   reconnects automatically. Firmware-completed events are not
   independently measured physical positions or safety-rated STOP.

A STOP submitted **after** a command is already sent must still be
handled by the firmware. Host-side generation checks cannot retract an
accepted command, guarantee device braking or prevent an entirely
separate unauthorized host process from accessing the serial port.
These remain separate firmware/physical validation and device-ownership
tasks; do not claim the new API solves them.

## Software tests and deferred physical qualification

Run the native, no-device tests:

```bash
python -m pytest tests/test_external_control.py \
  tests/test_playback.py tests/test_routed_serial.py -q
python -m pytest -q
ruff check .
mypy
```

Targeted regressions cover stale-generation denial across four native
commands, STOP while NeoHEX discovery is paused, STOP during asset
revision preflight, failed STOP inhibition, invalid/bool tokens, partial
serial writes, and the absence of automatic retry.

Hardware work is **not** part of this change. Host-loss behavior,
recovering/reopening an uncertain serial session, exclusive ownership
across processes, physically measured settling and servo-specific
watchdog/braking remain unqualified. Use an operator-attended local
Codex hardware plan with explicit approval before any firmware flash
or physical motion. Avoid introducing safety-rated claims.
