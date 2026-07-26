# stackchan-control-sdk

Host-side Python SDK, protocol documentation, and companion firmware extension for deterministic external control of M5Stack StackChan.

## Scope

This repository exposes **StackChan-native capabilities**:

- yaw and pitch motion
- eye and mouth feature updates
- native animation/dance keyframes
- RGB lighting
- stock Avatar WebSocket packet framing
- mocks for development without hardware
- a pinned external-control firmware overlay
- a staged USB hardware capability probe

It intentionally does **not** define AgenticForge emotions, character personalities, scene directions, dialogue, or WAV playback. Those belong in `robo-puppeteer` and `robo-director`.

## Current status

The upstream firmware already has the useful behavior engine. The stock Avatar app accepts avatar JSON, motion JSON, and dance sequences and routes them into the existing StackChan runtime. Stock firmware connects outward to M5Stack's cloud relay rather than exposing a supported local endpoint.

This repository now contains the software needed up to the physical-hardware boundary:

1. typed native packet and JSON models;
2. mock and generic WebSocket transports;
3. an upstream audit pinned to a public M5Stack commit;
4. a reproducible firmware overlay that adds an **EXT CONTROL** app;
5. USB Serial/JTAG request, response, state, stop, and completion handling;
6. a conservative capability-test CLI and evidence report.

The overlay is not yet claimed to work on retail hardware. The remaining gate is to build/flash it and plug in StackChan to identify the exposed USB data port and observe its real behavior.

## Python example

```python
from stackchan_control import AvatarUpdate, FeatureUpdate, StackChan
from stackchan_control.transports import MemoryTransport

transport = MemoryTransport()

async with StackChan(transport) as robot:
    await robot.set_pose(yaw=20, pitch=45, speed=25)
    await robot.update_avatar(
        AvatarUpdate(mouth=FeatureUpdate(size=8))
    )
```

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

## Development

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
