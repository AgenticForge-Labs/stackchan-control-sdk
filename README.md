# stackchan-control-sdk

Host-side Python SDK, protocol documentation, and companion firmware work for deterministic external control of M5Stack StackChan.

## Scope

This repository exposes **StackChan-native capabilities**:

- yaw and pitch motion
- eye and mouth feature updates
- native animation/dance keyframes
- RGB-light values embedded in animation keyframes
- packet framing for the stock Avatar WebSocket protocol
- mocks for development without hardware
- the planned local external-control firmware extension

It intentionally does **not** define AgenticForge emotions, character personalities, scene directions, dialogue, or WAV playback. Those belong in `robo-puppeteer` and `robo-director`.

## Current status

The upstream firmware already has the useful behavior engine. The stock Avatar app accepts binary WebSocket message types for avatar JSON, motion JSON, and dance sequences, then routes them to `StackChan::updateAvatarFromJson`, `StackChan::updateMotionFromJson`, and the existing animation parser.

The limitation is transport: stock firmware connects outward to M5Stack's cloud relay. This repository therefore starts with:

1. a tested implementation of the native packet and JSON formats;
2. a mock transport for Puppeteer development;
3. an explicit audit of the stock firmware path;
4. a design for a small local external-control firmware app.

It does **not** claim that an unmodified retail StackChan can already be controlled directly from a local Python process.

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

A generic `WebSocketTransport` is included for a compatible relay or the future local firmware endpoint. It deliberately does not embed undocumented M5Stack cloud authentication.

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

Do not rewrite StackChan firmware. Maintain a thin extension of M5Stack's MIT-licensed ESP-IDF firmware that adds a local, deterministic control endpoint and reuses the existing motion, avatar, animation, calibration, and hardware code.

See:

- [`docs/upstream-audit.md`](docs/upstream-audit.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`protocol/stock-avatar-websocket.md`](protocol/stock-avatar-websocket.md)
- [`protocol/external-control-v1.md`](protocol/external-control-v1.md)
- [`firmware/README.md`](firmware/README.md)

## License

AgenticForge Labs code in this repository is MIT licensed. M5Stack code incorporated later must retain its original copyright and MIT notices. See [`NOTICE`](NOTICE).
