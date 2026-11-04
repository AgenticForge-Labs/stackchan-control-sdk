# Development plan

These priorities describe outstanding work, not permission to move or flash a device. See [STATUS.md](STATUS.md) for the dated development history and [hardware capability testing](docs/hardware-capability-test.md) for documented evidence and procedures.

- Complete operator-attended USB, firmware, motion and display acceptance for the actual connected device and its advertised capabilities. Existing tests do not establish independent positioning accuracy, host-loss behavior or safe reconnects.
- Validate optional face scale on compatible firmware and obtain visual acceptance before treating it as available on a particular unit. Do not update or flash firmware automatically.
- Continue to evaluate host-loss handling, stop behavior and recovery; preserve unknown-outcome handling and avoid automatic reconnect or motion retry.
- Maintain reproducible, manually installed firmware packaging while documenting remaining build dependency and toolchain reproducibility limitations.
- Keep native protocol and device controls in this SDK. [Forge Puppeteer](https://github.com/AgenticForge-Labs/forge-puppeteer) owns optional semantic expression, multi-performer coordination and MCP integration.
