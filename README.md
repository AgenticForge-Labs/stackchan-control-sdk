# stackchan-control-sdk

Host-side Python SDK, protocol documentation, and companion firmware extension for deterministic external control of M5Stack StackChan.

## Scope

This repository exposes **StackChan-native capabilities**:

- yaw and pitch motion
- eye and mouth feature updates
- complete native animation/dance keyframes
- built-in RGB lighting and a 37-pixel NeoHEX on Port A
- stock Avatar WebSocket packet framing
- mocks for development without hardware
- a pinned external-control firmware overlay
- a staged USB hardware capability probe

It intentionally does **not** define AgenticForge emotions, character personalities, scene directions, dialogue, or WAV playback. Those belong in `forge-puppeteer` and `forge-studios`.

## Current status

The upstream firmware already has the useful behavior engine. The stock Avatar app accepts avatar JSON, motion JSON, and dance sequences and routes them into the existing StackChan runtime. Stock firmware connects outward to M5Stack's cloud relay rather than exposing a supported local endpoint.

This repository now contains the software needed up to the physical-hardware boundary:

1. typed native packet and JSON models;
2. mock and generic WebSocket transports;
3. an upstream audit pinned to a public M5Stack commit;
4. a reproducible firmware overlay that adds an **EXT CONTROL** app;
5. USB Serial/JTAG request, response, state, stop, validation, and completion handling;
6. a conservative capability-test CLI and evidence report;
7. a successful full build under ESP-IDF 5.5.4 with retained flash artifacts.

The first retail USB session on 2026-10-28 passed handshake, operator-confirmed
face and lighting updates, bounded yaw/pitch motion, and visual restoration.
Matching command completion and stop acknowledgments were recorded, including
a supervised active-motion cancellation and restoration follow-up. This is
initial hardware evidence: independent positioning accuracy, reconnects, and
host-loss behavior remain unverified. See
[`docs/hardware-capability-test.md`](docs/hardware-capability-test.md).

## Angle units

M5Stack's native servo JSON represents angles as integer **tenths of a degree**. For example, native `450` means 45°. The high-level `StackChan.set_pose()` API accepts ordinary degrees and converts them. Lower-level `ServoUpdate.angle` and the external-control JSON protocol use native tenths.

Continuous-rotation commands and custom spring parameters are deliberately disabled in external-control protocol v1. Position commands are validated against the upstream native limits before reaching the servos.

## Python example

```python
from stackchan_control import AvatarUpdate, FeatureUpdate, StackChan
from stackchan_control.transports import MemoryTransport

transport = MemoryTransport()

async with StackChan(transport) as robot:
    # Degree-based convenience API; serialized as yaw=200 and pitch=450.
    await robot.set_pose(yaw=20, pitch=45, speed=25)
    await robot.update_avatar(
        AvatarUpdate(mouth=FeatureUpdate(size=8))
    )
```

Partial native animation keyframes are rejected. The upstream parser supplies defaults for omitted fields, including fields that are unsafe to guess, so each transmitted frame must explicitly include both eyes, mouth, yaw, pitch, and servo speeds.

## Hardware-ready workflow

Prepare and build the pinned M5Stack firmware with the AgenticForge overlay:

```bash
python tools/prepare_firmware.py --refresh --build
```

After flashing and opening **EXT CONTROL** on StackChan, begin with a non-moving test:

```bash
pip install -e '.[serial]'
stackchan-probe ports
stackchan-probe hello --port /dev/ttyACM0
```

Then test face and lights without servo movement:

```bash
stackchan-probe run \
  --port /dev/ttyACM0 \
  --output hardware-reports/first.json
```

Motion is opt-in and deliberately limited to small ranges:

```bash
stackchan-probe run \
  --port /dev/ttyACM0 \
  --allow-motion \
  --output hardware-reports/first-motion.json
```

See [`docs/hardware-capability-test.md`](docs/hardware-capability-test.md) before connecting or flashing hardware.

## External NeoHEX shows

With one NeoHEX 37 connected to side Port A, extension 0.3.0 adds bounded
per-pixel lighting over USB. After the dim hardware check:

```bash
python tools/neohex_show.py --port DETECTED_PORT --show all \
  --brightness 8 --seconds 6 --output hardware-reports/neohex-shows.json
```

See [NeoHEX setup, limits, and timeout](docs/neohex.md). This leaves the face
and servos unchanged.

## Development

The driver regression test also requires a C++ compiler (`c++`).

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
mypy
```

## Firmware strategy

Do not rewrite StackChan firmware. The overlay adds one launcher app and one local transport while reusing M5Stack's existing motion, avatar, animation, calibration, and hardware code. The full upstream tree is fetched at the commit in `firmware/upstream.lock.json`, so upstream attribution and history remain clear.

See:

- [`docs/upstream-audit.md`](docs/upstream-audit.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/hardware-capability-test.md`](docs/hardware-capability-test.md)
- [`protocol/stock-avatar-websocket.md`](protocol/stock-avatar-websocket.md)
- [`protocol/external-control-v1.md`](protocol/external-control-v1.md)
- [`firmware/README.md`](firmware/README.md)

## License

AgenticForge Labs code in this repository is MIT licensed. M5Stack code remains upstream and any prepared or distributed modified firmware must retain M5Stack's original copyright and MIT notices. See [`NOTICE`](NOTICE).

## USB external-control facade

The `ExternalControl` facade uses `RoutedSerialClient` for the EXT CONTROL USB
protocol; it is separate from the stock packet `StackChan` API. Open it explicitly
with `RoutedSerialClient.open(port)` and close the client after use. The installed
`stackchan` command exposes discovery, state, head, face, builtin lights, NeoHEX,
and stop; run `stackchan --help` and `stackchan --port PORT COMMAND --help` for
arguments. Outputs and runtime errors are JSON. For example:

```bash
stackchan --port /dev/ttyACM0 discover
stackchan --port /dev/ttyACM0 state
stackchan --port /dev/ttyACM0 face --feature mouth --size 10
```

Head targets use integer tenths of a degree and a mandatory native speed. They
are checked against protocol bounds and the current firmware-reported limits.
Face, lights, and motion are separate typed operations. The firmware's reported
positions and completion are its model/servo state, not independent measurement.
The SDK has no automatic reconnect or motion retry: timeout or connection loss
leaves the command outcome unknown. A pending unknown motion inhibits another
motion in the same facade. Failed or unconfirmed stop inhibits further motion in
that facade; inspect the device and resolve safety before creating a new session.
A stop request bypasses motion waiting and invalidates motion preflight. Hardware
stop behavior and host-loss handling are not safety-rated or fully qualified.
The single NeoHEX frame operation does not sustain lighting: firmware clears it
unless refreshed within its advertised watchdog period. Native animation remains
gated. Do not run simultaneous clients against the same serial port.

## Local native assets

`stackchan assets --pack examples/assets` lists the explicitly selected pack
without opening serial. Each JSON file contains a versioned pose or sequence of
host-driven typed face, head, or built-in light operations. The loader rejects
invalid, out-of-order, oversized, duplicate, and unsupported assets and returns a
SHA-256 revision of the original file. These are example data, not a firmware
emotion library or evidence of hardware suitability.
Catalog descriptors use `stackchan/`-prefixed IDs, report resources derived
from the steps, and mark device compatibility as unchecked. Duration is unknown:
the last requested start time is not evidence that movement has completed.
Playback checks that the in-memory asset still matches its original file snapshot
and revision; reloading changed file contents produces a different revision.

An operator can select an exact ID and revision with `stackchan --port PORT play
--pack PACK --id ID --revision sha256:...`. The Python equivalent is `load_asset`
or `list_assets` followed by `play_asset(robot, asset, expected_revision=...)`.
Playback validates the entire in-memory asset and revision before the first
operation, then executes steps sequentially, rechecking device capabilities and
motion limits on each operation. Late steps are explicitly delayed until the prior
step completes; result records include requested and observed host timings. This is
not a hard real-time scheduler. A concurrent `robot.stop()` interrupts future
steps; its result must be checked separately. If an operation fails or times out,
playback raises immediately and does not infer a safe outcome or automatically
retry; the caller remains responsible for requesting and verifying stop. Native
firmware animation is still gated and is never used for these assets.

For sustained NeoHEX output, `sustain_neohex` and the `neohex --duration`
option refresh against the firmware-advertised watchdog and explicitly clear the
frame. See [NeoHEX details](docs/neohex.md) for cancellation and failure semantics.
