# Architecture

## Repository boundary

```text
forge-studios
  owns scene timelines and WAV playback
        |
forge-puppeteer
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

### Concurrent external-control event routing

`RoutedSerialClient` is a separate USB external-control transport, not the stock
packet transport. It owns one serial reader and routes events by command ID;
callers may submit `system.stop` while a motion is pending. `wait()` returns the
terminal events including firmware failures and cancellations. A timeout or lost
connection leaves the outcome unknown, and a later event can be inspected through
`wait()` or `events()` while the connection remains alive. There is no automatic
reconnect or command retry. The caller must explicitly close the client. This is a
transport primitive, not yet the validated native-control facade or a hardware
safety guarantee. The reader requires a finite wire timeout for timely shutdown.

The `ExternalControl` facade uses the router with separate native face, head,
built-in light, and NeoHEX methods. Capabilities are intersected with an explicit
host allowlist; unknown firmware capabilities are not promoted to controls.
Motion is admitted one at a time, checked against live firmware-reported limits,
and invalidated if stop is requested during preflight. An unconfirmed stop
inhibits subsequent motion for that facade instance. State and completion are
firmware-reported and do not constitute independently measured settling.

The SDK capability registry includes versioned JSON Schemas for the supported
USB wire payloads. CLI discovery returns those schemas only for controls also
advertised by the connected firmware. The schemas describe static host protocol
bounds; device-reported limits and the typed facade's validation remain mandatory
at execution. JSON Schema integer handling may accept numerically integral JSON
floats; the typed facade additionally requires actual integers for native servo
and face values. Importing or inspecting the registry does not open a device.

USB writes have a finite configured timeout and are serialized. The router does
not perform a blocking output-drain operation after each write; a successful write
is not completion evidence, and only a terminal firmware event supplies that
outcome. A failed or partial write leaves the outcome unknown and makes the
connection unavailable. These bounds are transport safeguards, not a guaranteed
stop latency or physical stop qualification.
