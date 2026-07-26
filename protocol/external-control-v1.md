# External Control Protocol v1

Status: implemented in the firmware overlay; hardware validation pending.

The local firmware extension uses newline-delimited JSON over ESP32-S3 USB Serial/JTAG. Because ESP-IDF logs may share the port, every protocol line starts with `@AF `.

## Commands

- `system.hello`
- `system.capabilities`
- `system.ping`
- `system.state`
- `system.stop`
- `avatar.update`
- `motion.update`
- `lights.update`
- `animation.play`
- `animation.stop`

## Command envelope

```text
@AF {"id":"cmd-42","method":"motion.update","params":{"yawServo":{"angle":20,"speed":120},"pitchServo":{"angle":45,"speed":120}}}
```

`id` is an opaque host-generated string. `params` uses the same native JSON shapes already parsed by the M5Stack firmware.

## Events

```text
@AF {"id":"cmd-42","event":"accepted"}
@AF {"id":"cmd-42","event":"completed"}
```

A rejected or malformed command returns:

```text
@AF {"id":"cmd-42","event":"failed","detail":"unsupported method"}
```

The firmware emits an unsolicited ready event when the service starts:

```text
@AF {"event":"ready","protocol_version":"1.0","transport":"usb_serial_jtag"}
```

## Completion semantics

- avatar and lighting updates complete after they have been applied to the native model
- motion completes when both native servos report settled, with a short fallback for no-op moves
- animation completes when its `DanceModifier` is removed by the native modifier pool
- `system.stop` removes active animation and commands both servos to hold their current angles

These semantics must be checked on the retail device before they are treated as production guarantees.

## Safety constraints

- the host probe does not move servos unless `--allow-motion` is supplied
- the first probe uses yaw only through ±12 degrees and pitch only from 35 to 55 degrees
- normal application-level limits remain the responsibility of the SDK and firmware motion layer
- any disconnect watchdog behavior beyond app exit remains follow-up work after the first hardware test
