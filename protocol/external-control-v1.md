# External Control Protocol v1

Status: implemented and build-verified in the firmware overlay; retail hardware validation pending.

The local firmware extension uses newline-delimited JSON over ESP32-S3 USB Serial/JTAG. Because ESP-IDF logs may share the port, every protocol line starts with `@AF `.

## Active commands

- `system.hello`
- `system.capabilities`
- `system.ping`
- `system.state`
- `system.stop`
- `avatar.update`
- `motion.update`
- `lights.update`
- `animation.stop`

`animation.play` is recognized but deliberately returns `failed` until complete current eye, mouth, and servo keyframes can be constructed and observed on the retail unit. The public M5Stack parser supplies defaults for omitted keyframe fields, so partial keyframes are unsafe.

## Native angle units

Servo `angle` values are integer **tenths of a degree**:

- `200` means 20°
- `-120` means −12°
- `450` means 45°

Protocol-v1 position limits mirror the pinned upstream firmware:

- yaw: `-1280..1280` (−128°..128°)
- pitch: `30..870` (3°..87°)
- speed: `0..1000`

Continuous rotation and custom spring parameters are rejected by this local protocol even though lower-level upstream APIs support them.

## Command envelope

```text
@AF {"id":"cmd-42","method":"motion.update","params":{"yawServo":{"angle":200,"speed":120},"pitchServo":{"angle":450,"speed":120}}}
```

`id` is an opaque host-generated string. `params` uses the native JSON names parsed by the M5Stack firmware.

Only one motion request may be pending. A second request receives `failed` with `motion controller is busy` rather than replacing the first request's completion identity.

## Events

```text
@AF {"id":"cmd-42","event":"accepted"}
@AF {"id":"cmd-42","event":"completed"}
```

A rejected or malformed command returns `failed` without first being accepted:

```text
@AF {"id":"cmd-42","event":"failed","detail":"pitchServo angle is outside the native safety limits"}
```

A pending motion stopped by `system.stop` receives:

```text
@AF {"id":"cmd-42","event":"cancelled","detail":"stopped by system.stop"}
```

The firmware emits an unsolicited ready event when the service starts:

```text
@AF {"event":"ready","protocol_version":"1.0","transport":"usb_serial_jtag"}
```

## State response

`system.state` returns:

- `yaw_angle_tenths` and `pitch_angle_tenths`
- readable `yaw_degrees` and `pitch_degrees`
- current runtime native angle limits
- movement flags
- current left-eye, right-eye, and mouth fields

The hardware probe uses the raw tenths values to restore the exact reported servo targets and uses the avatar snapshot to restore the face fields it changes.

## Completion semantics

- avatar and lighting updates complete after being applied to the native model
- motion completes when both native servos report settled, with a short fallback for a no-op move
- `system.stop` cancels a pending motion request and commands both servos to hold their current angles
- native animation completion remains gated until complete retail keyframes are validated

These semantics must be checked on the retail device before they are treated as production guarantees.

## Safety constraints

- the host probe does not move servos unless `--allow-motion` is supplied
- the first probe commands yaw only through ±120 native units (±12°)
- the first probe commands pitch only from 350 to 550 native units (35°..55°)
- each first-session motion command specifies both axes explicitly
- protocol v1 rejects out-of-range position commands, continuous rotation, and custom springs
- the service rejects concurrent motion commands instead of orphaning completion events
- face tests begin from a reported state snapshot and restore the fields they change
- disconnect watchdog behavior beyond app exit remains follow-up work after the first hardware test
