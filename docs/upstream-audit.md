# Upstream firmware audit

Audit target: `m5stack/StackChan` at commit `b72b3ede38b32d54f0b6ba51c62cfcef2ec3ae1e`.

## Confirmed reusable paths

### Core object

`firmware/main/stackchan/stackchan.h` owns attached motion and avatar implementations and exposes:

- `updateAvatarFromJson`
- `updateMotionFromJson`
- `updateNeonLightFromJson`
- modifier management
- a shared update loop

### Avatar app

`firmware/main/apps/app_avatar/app_avatar.cpp` starts the WebSocket Avatar service and connects events as follows:

- WebSocket avatar data -> `updateAvatarFromJson`
- WebSocket motion data -> `updateMotionFromJson`
- WebSocket dance data -> `parse_sequence_from_json` -> `DanceModifier`
- BLE avatar and motion data -> the same native JSON update functions

This proves the existing behavior implementation is already transport-neutral below the HAL event layer.

### Stock WebSocket service

`firmware/main/hal/hal_ws_avatar.cpp` defines binary message types including:

- `0x03` ControlAvatar
- `0x04` ControlMotion
- `0x14` DanceSequence
- `0x10` / `0x11` heartbeat

The stock service connects outward to an M5Stack server URL and uses a generated authorization token. It is therefore not a documented local WebSocket server that a Python process can simply connect to on the robot.

### JSON formats

`firmware/main/stackchan/json/json_helper.cpp` confirms:

- avatar features: `x`, `y`, `rotation`, `weight`, `size`
- top-level avatar keys: `leftEye`, `rightEye`, `mouth`
- servo modes: `rotate`, or `angle` with optional `speed`, or `angle` with spring parameters
- top-level motion keys: `yawServo`, `pitchServo`
- animation keyframes: avatar features, yaw/pitch servo values, left/right RGB colors, and `durationMs`

## Decision

Do not build new robot behavior firmware. Add a thin local transport adapter around these existing native calls.

## What remains unverified

- The mobile/cloud session and device-discovery protocol.
- Whether current retail firmware exactly matches the public commit.
- Whether a local direct-control mode can be installed as a downloadable app without rebuilding the full image.
- Hardware timing and safe stop behavior on a physical StackChan.

These require either a device or a full ESP-IDF build environment. The SDK does not disguise those unknowns.
