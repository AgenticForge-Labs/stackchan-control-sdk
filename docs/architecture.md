# Architecture

## Repository boundary

```text
robo-director
  owns scene timelines and WAV playback
        |
robo-puppeteer
  owns character intent and semantic performances
        |
stackchan-control-sdk
  owns native StackChan commands, units, and protocol
        |
companion firmware extension
  owns local transport, validation, execution, and status
        |
M5Stack StackChan firmware
  owns avatar rendering, motion, animation, calibration, and hardware
```

`stackchan-control-sdk` must never need to know what “skeptical,” “laughing at Reachy,” or “watching the printer” means. Puppeteer composes those performances from native updates and complete native sequences.

## Units boundary

The M5Stack wire format uses integer tenths of a degree for servo angles. The high-level Python `set_pose()` method accepts ordinary degrees and converts them, while low-level native models and the firmware protocol retain the upstream integer representation. State responses include both forms to avoid ambiguity.

## Transport phases

### Phase 0: mock

`MemoryTransport` allows host integration and protocol tests without hardware.

### Phase 1: stock-protocol experiment

Reproduce the binary frames and JSON accepted by the existing Avatar app. A compatible relay may be used experimentally, but undocumented M5Stack cloud authentication is not part of the public SDK contract.

### Phase 2: local external-control firmware

The implemented first endpoint uses ESP32-S3 USB Serial/JTAG with prefixed newline-delimited JSON. A later LAN WebSocket endpoint may use the same command and event semantics.

The local protocol deliberately exposes a smaller surface than the upstream internal APIs. Protocol v1 allows bounded position motion but rejects continuous rotation and custom spring parameters. Animation playback remains gated until every keyframe field can be populated safely from observed retail state.

## Safety ownership

Host-side checks improve usability but are not the safety boundary. Firmware validates native angle and speed ranges, rejects concurrent motion commands, and prevents dangerous motion modes from entering the upstream parser. Rate limits, a host-loss watchdog, reconnect behavior, and hardware-observed settling rules remain firmware work after the first physical test.
