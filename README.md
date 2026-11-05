# StackChan Control SDK

**Control StackChan from AI agents through a standard MCP interface with [Forge Puppeteer](https://github.com/AgenticForge-Labs/forge-puppeteer), or use this SDK directly for native device control.**

Puppeteer gives agents tool calls for supported native robot capabilities and shared behaviors, actions, and emotions across open-source robots. Inspired by [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) and the [Reachy Mini Conversation App](https://github.com/pollen-robotics/reachy_mini_conversation_app), it generalizes conversational robot performance across devices. Available tools depend on the selected server, device capabilities, configuration and operator grants.

StackChan Control SDK is a host-side Python toolkit, command-line interface, protocol reference and companion firmware extension for the M5Stack StackChan desktop robot. It exposes native head, face and lighting controls so developers can build interactive applications, create repeatable behaviors and experiment without hardware.

## What you can do

- Control supported yaw and pitch movements and update the eyes and mouth.
- Use built-in RGB lights and a supported NeoHEX 37 light on Port A.
- Work with typed native packets, the stock Avatar WebSocket framing, and the USB external-control protocol.
- List and replay explicitly selected native pose and sequence assets using their content revisions.
- Develop against a memory transport and test without connecting a robot.

The stock packet API and the USB `ExternalControl` facade use different transports. The USB features require compatible EXT CONTROL firmware and advertised capabilities. Native firmware animation remains gated in the external-control protocol; availability varies by firmware. See [Architecture](docs/architecture.md) and [USB protocol](protocol/external-control-v1.md).

## Try it without hardware

Requires Python 3.11 or newer.

```bash
git clone https://github.com/AgenticForge-Labs/stackchan-control-sdk.git
cd stackchan-control-sdk
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

This example uses a memory transport; it does not connect to a robot:

```python
import asyncio

from stackchan_control import AvatarUpdate, FeatureUpdate, StackChan
from stackchan_control.transports import MemoryTransport

async def main():
    transport = MemoryTransport()
    async with StackChan(transport) as robot:
        await robot.set_pose(yaw=20, pitch=45, speed=25)
        await robot.update_avatar(AvatarUpdate(mouth=FeatureUpdate(size=8)))

asyncio.run(main())
```

The high-level `set_pose()` uses degrees; low-level native servo values use integer tenths of a degree. See [Architecture](docs/architecture.md) for the units and transport boundaries.

## Connect a StackChan

Install the serial extra with `pip install -e '.[serial]'`. The local USB workflow requires compatible firmware with the **EXT CONTROL** app. Read the [hardware capability test](docs/hardware-capability-test.md), [firmware guide](firmware/README.md), and [firmware installation guidance](docs/firmware-release.md) before preparing or flashing firmware. Flashing is a separate manual action.

With a compatible device and EXT CONTROL running, begin with discovery:

```bash
stackchan-probe ports
stackchan-probe hello --port /dev/ttyACM0
stackchan --port /dev/ttyACM0 discover
stackchan --port /dev/ttyACM0 state
```

Choose the actual port for your device. If EXT CONTROL is missing, consult the [recovery guide](docs/disappearing-app-recovery.md) before considering a flash.

Physical motion requires an attentive operator and device-specific review. Firmware-reported positions are not independent measurements, and STOP and host-loss behavior are not safety-rated or fully qualified. A timeout or lost connection can leave the outcome unknown; inspect the device rather than retrying automatically. Do not run simultaneous clients on the same serial port.

## Working with Forge Puppeteer

The SDK is independently usable from Python and the CLI. [Forge Puppeteer](https://github.com/AgenticForge-Labs/forge-puppeteer) adds optional semantic expression, coordinated multi-robot performance and an MCP interface for agents. StackChan's native protocol, device capabilities and execution safeguards remain in this SDK and its firmware; personalities and higher-level performances belong to the application.

## Explore

- [Hardware testing and safety](docs/hardware-capability-test.md)
- [Firmware releases](docs/firmware-release.md) and [recovery](docs/disappearing-app-recovery.md)
- [Architecture](docs/architecture.md), [stock Avatar protocol](protocol/stock-avatar-websocket.md), and [USB external-control protocol](protocol/external-control-v1.md)
- [Execution state and STOP fencing](docs/execution-state.md)
- [NeoHEX setup and limits](docs/neohex.md)
- [Current status and history](STATUS.md) and [development plan](PLAN.md)

## Acknowledgments

Thanks to the [Stack-chan community](https://github.com/stack-chan/stack-chan) and [M5Stack StackChan](https://github.com/m5stack/StackChan) for the open robot and firmware, and to [Pollen Robotics](https://github.com/pollen-robotics/reachy_mini) for Reachy Mini and its [Conversation App](https://github.com/pollen-robotics/reachy_mini_conversation_app), which inspire Puppeteer's shared approach.

## License

AgenticForge Labs code in this repository is MIT licensed. Prepared or distributed modified firmware must retain M5Stack's original copyright and MIT notices. See [NOTICE](NOTICE).
