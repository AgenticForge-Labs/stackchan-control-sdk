# StackChan hardware capability test

This is the handoff point between software-only validation and physical hardware validation. The test is deliberately staged so connecting the robot does not immediately move it.

## Before connecting

1. Build and flash the prepared firmware described in `firmware/README.md`.
2. Place StackChan on a clear, stable surface with at least 30 cm of clearance around its head.
3. Verify that cables cannot catch on the rotating base.
4. Do not manually force either servo while torque may be enabled.
5. Keep a hand near the power switch during the first motion test.

## Stage 1: identify the port

```bash
pip install -e '.[serial]'
stackchan-probe ports
```

The likely device should mention M5Stack, Espressif, USB Serial, or USB JTAG. Record all ports before and after plugging in if identification is ambiguous.

## Stage 2: non-moving handshake

Open **EXT CONTROL** from the StackChan launcher, then run:

```bash
stackchan-probe hello --port /dev/ttyACM0
```

On Windows, use a port such as `COM6`. This confirms only transport and firmware identity. It must not move the robot.

## Stage 3: display and lighting tests

```bash
stackchan-probe run --port /dev/ttyACM0 --output hardware-reports/first.json
```

This changes the eyes, mouth, and lights but skips all servo tests. The interactive prompts record whether each visible behavior actually happened.

## Stage 4: conservative motion tests

Only after inspecting the mechanism and confirming Stage 3:

```bash
stackchan-probe run \
  --port /dev/ttyACM0 \
  --allow-motion \
  --output hardware-reports/first-motion.json
```

The sequence centers the robot, moves yaw only through ±12 degrees, and moves pitch only between 35 and 55 degrees. These are intentionally smaller than the firmware limits.

Stop immediately if motion binds, chatters, pulls a cable, moves in the wrong direction, or fails to stop. Power-cycle the robot before further testing.

## Evidence to capture

For each run, preserve:

- the generated JSON report
- host operating system and port name
- retail StackChan firmware version before flashing
- our pinned upstream commit and resulting firmware build SHA
- a short phone video showing face, lights, yaw, and pitch behavior
- any unexpected sounds, vibration, overshoot, or cable interference

## Decisions after the first physical run

The report determines the next implementation step:

- USB port works reliably: finish request/response transport and reconnect handling.
- USB port is not wired to native USB Serial/JTAG: test the CoreS3 USB connector or switch to local WebSocket control.
- native animation completion is reliable: expose awaited animation calls in the Python SDK.
- servo completion is noisy or inaccurate: use tolerance and settling-time completion logic.
- avatar JSON differs from the public repository: capture retail payloads and update the models.
- lights or face fields are incomplete: expand the native capability schema without adding AgenticForge character semantics.
