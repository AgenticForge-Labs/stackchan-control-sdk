# StackChan hardware capability test

This is the handoff point between software-only validation and physical hardware validation. The test is deliberately staged so connecting the robot does not immediately move it.

The pinned overlay has already completed a full ESP-IDF 5.5.4 build. The remaining questions are physical: which connector exposes USB Serial/JTAG, whether the image flashes and launches on the retail unit, and whether observed motion and rendering match the public source.

## Before connecting

1. Record the retail firmware version and any calibration/settings before flashing.
2. Preserve or locate M5Stack's official recovery method before replacing the factory image.
3. Build or download the prepared firmware described in `firmware/README.md`.
4. Place StackChan on a clear, stable surface with at least 30 cm of clearance around its head.
5. Verify that cables cannot catch on the rotating base.
6. Do not manually force either servo while torque may be enabled.
7. Keep a hand near the power switch during the first motion test.

## Important angle convention

The external-control JSON uses M5Stack's native integer **tenths of a degree**. Thus `450` means 45°, `120` means 12°, and `350` means 35°. The probe already uses the converted native values; do not replace them with whole-degree numbers in raw JSON.

## Stage 1: identify the port

```bash
pip install -e '.[serial]'
stackchan-probe ports
```

The likely device should mention M5Stack, Espressif, USB Serial, or USB JTAG. Record all ports before and after plugging in if identification is ambiguous. Test both the CoreS3 and body connectors if necessary, but do not assume both carry the same USB data signals.

## Stage 2: non-moving handshake

Open **EXT CONTROL** from the StackChan launcher, then run:

```bash
stackchan-probe hello --port /dev/ttyACM0
```

On Windows, use a port such as `COM6`. This confirms only transport and firmware identity. It must not move the robot. The response should report `native_angle_unit` as `tenths_of_a_degree`.

## Stage 3: display and lighting tests

```bash
stackchan-probe run --port /dev/ttyACM0 --output hardware-reports/first.json
```

This changes the eyes, mouth, and lights but skips all servo tests. The interactive prompts record whether each visible behavior actually happened. The probe snapshots and restores the eye and mouth fields it changes, then turns both test lights off.

## Stage 4: conservative motion tests

Only after inspecting the mechanism and confirming Stage 3:

```bash
stackchan-probe run \
  --port /dev/ttyACM0 \
  --allow-motion \
  --output hardware-reports/first-motion.json
```

The sequence sends these native targets:

- centered pose: yaw `0`, pitch `450` (45°)
- yaw sweep: `-120`, `120`, `0` (−12°, 12°, 0°)
- pitch sweep: `350`, `550`, `450` (35°, 55°, 45°)
- restoration: the exact raw yaw and pitch values reported before testing

These are intentionally smaller than the upstream firmware limits. The firmware extension independently rejects yaw outside `-1280..1280`, pitch outside `30..870`, speed outside `0..1000`, continuous rotation, custom springs, and concurrent motion requests.

Stop immediately if motion binds, chatters, pulls a cable, moves in the wrong direction, or fails to stop. Power-cycle the robot before further testing.

## Evidence to capture

For each run, preserve:

- the generated JSON report
- host operating system and port name
- which physical connector was used
- retail StackChan firmware version before flashing
- our pinned upstream commit and resulting firmware build SHA
- the exact flash command or flasher used
- a short phone video showing face, lights, yaw, and pitch behavior
- any unexpected sounds, vibration, overshoot, or cable interference

## Decisions after the first physical run

The report determines the next implementation step:

- USB port works reliably: add reconnect handling and a host-loss watchdog.
- USB port is not wired to native USB Serial/JTAG: test the other connector or switch to local WebSocket control.
- servo completion is noisy or inaccurate: replace the current `isMoving()` completion rule with angle tolerance plus settling time.
- current runtime limits differ from the pinned public source: use the reported limits and audit the retail firmware delta.
- complete native state is reliable: construct and test fully populated animation keyframes.
- avatar JSON differs from the public repository: capture retail payloads and update the models.
- lights or face fields are incomplete: expand the native capability schema without adding AgenticForge character semantics.

## Workstation preparation — 2026-10-28

Remote `main` was fetched and verified at
`36207e1be1879dcaa31ba5cae1f7155b65eba3e4`; no open PRs were found.
The Linux workstation enumerated an Espressif `303a:1001` USB Serial/JTAG
interface at `/dev/ttyACM1`. This is a candidate device identity, not a
successful protocol handshake; the operator confirmed the body USB connector. A separate QinHeng serial device must not be used for this probe.

The operator reported factory firmware v1.4.4 and no EXT CONTROL app. A full
16 MB flash backup was read and verified against the device (digest matched)
before installation. The NVS snapshot contains servo zero offsets 475 and 596,
with AI startup disabled. The original NVS partition matches the prepared layout
and is excluded from the flash manifest. Hidden settings remain in the private
local backup; post-install runtime calibration is not yet confirmed.
ESP-IDF 5.5.4 preparation/build passed locally using the CI container. The pinned
upstream identifies as 1.4.3, distinct from the retail 1.4.4 image. Installation
with `idf.py -p /dev/ttyACM1 flash` succeeded; all five image hashes verified.
Automatic post-flash reset left the unit in download mode with a blank screen;
passive USB output reported `waiting for download`. A brief manual RST press
resolved this, and the operator launched EXT CONTROL. No second flash was needed.

Local preparation logs and USB enumeration are retained under ignored
`hardware-reports/`, along with Python check results. Raw generated reports and
firmware binaries must remain outside source control.

Official recovery: [M5Stack StackChan documentation](https://docs.m5stack.com/en/StackChan)
describes restoring the official StackChan image through M5Burner. It also
describes entering download mode by holding RST for three seconds until the
indicator turns green, then releasing it. Both USB connectors support data;
M5Stack recommends the base connector. Record the installed version and settings
and obtain the appropriate official recovery image before flashing. Recovery to
a factory image does not establish preservation of device-specific settings.

Probe failures now abort further commands after a motion error, negative motion
observation, or interruption, and attempt `system.stop`. Restoration is skipped
after such an abort because it would issue another physical move. If stopping
cannot be confirmed or motion is abnormal, power off before further testing.
A normal completed run still restores the captured initial pose. Firmware-reported
angles and settled flags remain reported state until independently observed.


### First retail results

The SDK implementation tested was
`20e54995019825974952c922930bcbf5c68cfcc1` (subsequent commits document results).
Python validation passed: 23 tests, Ruff, and mypy. The exact local firmware
identity, hashes, configuration, and container digest are retained in
`hardware-reports/build-identity.json`; exact installation/backup/recovery commands
are in `hardware-reports/commands.txt`. The full factory backup is 16 MB and
passed an esptool digest comparison. These private generated artifacts remain
ignored and are not committed.

- `hello-first.log`: protocol 1.0, overlay 0.2.0, upstream V1.4.3, M5Stack
  StackChan board, USB Serial/JTAG, native tenths-of-degree units.
- `first.json`: face changes, original-face restoration, and distinct blue and
  orange/red lights confirmed by the operator. Lights-off and idle stop received
  accepted/completed events. Motion was disabled.
- `first-motion.json`: repeated face/light checks confirmed; centered 45° pitch,
  yaw −12°/+12°/0°, pitch 35°/55°/45°, and visual return to the initial pose all
  confirmed smooth by the operator. No chatter, binding, or cable pulling was
  reported. Each motion request received a matching accepted/completed pair.
  Continuous rotation and animation playback were not run.

Initial reported yaw/pitch were −2.1°/36.8°; final reported values before stop
were −0.9°/36.8°. Restoration commanded the exact captured raw initial values,
but final reported yaw differed by 1.2°. The operator confirmed visual return;
these observations do not establish independently measured absolute accuracy or
settling tolerance. Firmware state uses native feedback with a software fallback
on invalid feedback, so reported position must not be described as independent
measurement.

`system.stop` completed after motion had settled. In-flight cancellation and
physical interruption remain unverified; the current probe does not exercise
that case. No physical stall was induced. Active-stop validation requires a
separately reviewed bounded test before it is treated as proven. Reconnect and
host-loss watchdog behavior also remain follow-up work. USB worked throughout
both staged runs; these results do not justify adding another transport.

Integration status: **awaiting further hardware validation**. No Forge Puppeteer
integration was started. Organization-wide `architecture.md` and `development.md`
could not be located; repository architecture and current Puppeteer boundary
instructions were inspected instead.
