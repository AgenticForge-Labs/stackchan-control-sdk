# External Control Protocol v1

Status: design target for the companion firmware extension.

The stock protocol is efficient but lacks request identity, acknowledgments, capability discovery, and deterministic completion signals. The local firmware extension will wrap native behavior in newline-delimited JSON commands.

## Required commands

- `system.hello`
- `system.capabilities`
- `system.stop`
- `avatar.update`
- `motion.update`
- `animation.play`
- `animation.cancel`
- `state.get`

## Command envelope

```json
{
  "version": 1,
  "id": "cmd-42",
  "command": "motion.update",
  "payload": {
    "yawServo": {"angle": 20, "speed": 30},
    "pitchServo": {"angle": 45, "speed": 30}
  }
}
```

## Events

```json
{"version":1,"id":"cmd-42","event":"accepted"}
{"version":1,"id":"cmd-42","event":"completed"}
```

Errors include a stable code and human-readable message:

```json
{
  "version": 1,
  "id": "cmd-42",
  "event": "failed",
  "error": {"code": "INVALID_PITCH", "message": "pitch is outside configured limits"}
}
```

## Firmware requirements

- Commands call existing StackChan native APIs rather than duplicating behavior.
- `system.stop` cancels modifiers and active motion safely.
- A watchdog returns the device to configured idle behavior after host loss.
- Capability discovery reports firmware, protocol, board, and available native features.
- The first transport is USB CDC. LAN WebSocket is optional and must use the same messages.
