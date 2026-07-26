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
  owns native StackChan commands and protocol
        |
companion firmware extension
  owns local transport, validation, execution, and status
        |
M5Stack StackChan firmware
  owns avatar rendering, motion, animation, calibration, and hardware
```

`stackchan-control-sdk` must never need to know what “skeptical,” “laughing at Reachy,” or “watching the printer” means. Puppeteer composes those performances from native updates and sequences.

## Transport phases

### Phase 0: mock

`MemoryTransport` allows host integration and protocol tests without hardware.

### Phase 1: stock-protocol experiment

Reproduce the binary frames and JSON accepted by the existing Avatar app. A compatible relay may be used experimentally, but undocumented M5Stack cloud authentication is not part of the public SDK contract.

### Phase 2: local external-control firmware

Add a local USB CDC endpoint first, then optionally a LAN WebSocket endpoint. Both should accept the versioned external-control protocol and internally call the same native avatar, motion, and animation functions.

## Safety ownership

Host-side checks improve error messages but are not safety controls. Servo bounds, rate limits, watchdog behavior, and disconnect handling must live in firmware.
