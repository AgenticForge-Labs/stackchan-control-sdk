# Firmware extension

This directory contains an overlay for the public M5Stack StackChan ESP-IDF firmware. It does not duplicate the entire upstream repository. `upstream.lock.json` pins the exact upstream commit and `tools/prepare_firmware.py` creates a reproducible worktree.

The overlay and pinned upstream tree complete a full ESP-IDF 5.5.4 build in GitHub Actions. A first retail USB session passed flashing, handshake, face, lights, and bounded
motion checks on 2026-10-28. See `docs/hardware-capability-test.md` for evidence
and limits, including a successful supervised active-motion cancellation follow-up.

## What the overlay adds

The **EXT CONTROL** launcher app:

- creates the existing `DefaultAvatar`
- opens the ESP32-S3 USB Serial/JTAG data channel
- accepts newline-delimited JSON commands prefixed with `@AF `
- routes validated avatar, position-motion, and lighting data into existing M5Stack APIs
- reports accepted, completed, failed, cancelled, state, and capability events
- reports native angles in tenths of a degree plus readable degree values
- rejects out-of-range positions, continuous rotation, custom springs, and concurrent motion requests
- holds the current servo angles on exit or `system.stop`
- recognizes but gates native animation playback until complete retail keyframes are validated

It does not include character emotions, dialogue, audio playback, or AgenticForge scene logic.

## Prepare the pinned source tree

Install Git and ESP-IDF 5.5.4, then run:

```bash
python tools/prepare_firmware.py --refresh
```

The prepared project appears at:

```text
.firmware-worktree/StackChan/firmware
```

The preparation script asserts exact patch anchors. If M5Stack changes the pinned source, it fails rather than silently producing a partially patched firmware image.

## Build

With the ESP-IDF environment activated:

```bash
python tools/prepare_firmware.py --refresh --build
```

Equivalent manual commands:

```bash
cd .firmware-worktree/StackChan/firmware
python3 ./fetch_repos.py
idf.py build
```

The GitHub workflow also retains the build log, application image, bootloader, partition table, and `flasher_args.json`.

## Release bundle

After a successful clean source build, package the ESP-IDF flash inputs from the
SDK repository root:

```bash
python3 tools/package_firmware.py --output dist/stackchan-external-control-0.3.0.zip
```

The ZIP is for manual installation and includes `FLASHING.md`, `SHA256SUMS`,
a provenance/hash manifest, validated flash layout, and license notices. Before manual
flashing, extract and run `sha256sum -c SHA256SUMS`; abort if any hash fails. See `docs/firmware-release.md`
for reproducibility limitations and release prerequisites. Packaging does not
flash the device or alter NVS.

## Flash and restore

Do not flash until the retail device is available and its existing firmware version and settings have been recorded. The first physical session should identify which StackChan/CoreS3 USB connector exposes the ESP32-S3 USB Serial/JTAG port.

Flash the prepared image with:

```bash
idf.py -p PORT flash monitor
```

If flashing verifies successfully but the screen stays blank, inspect serial
output before reflashing. In the first retail session, automatic reset left the
ESP32-S3 reporting `waiting for download`. A brief press/release of RST booted
the installed firmware, and the operator then opened EXT CONTROL. Holding RST
enters download mode; do not hold it for a normal restart.

Keep the upstream repository and M5Stack's official flashing instructions available so the factory firmware can be restored.

## Wire protocol

Host command using native tenths of a degree (`450` = 45°):

```text
@AF {"id":"abc","method":"motion.update","params":{"yawServo":{"angle":0,"speed":100},"pitchServo":{"angle":450,"speed":100}}}
```

Firmware events:

```text
@AF {"id":"abc","event":"accepted"}
@AF {"id":"abc","event":"completed"}
```

Normal ESP-IDF logs may share the same serial port. Host software ignores lines without the `@AF ` prefix.

See `docs/hardware-capability-test.md` for the exact plug-in test sequence.


## Filming layout

EXT CONTROL enlarges the stock avatar uniformly by approximately 1.7× about the
screen center. Native feature parameters continue to use their existing units.
Face updates invalidate the full screen to prevent stale pixels around shrinking
features on the scaled panel. A talking/surprised replay initially exposed mouth
streaks; the operator confirmed a clean replay after this redraw change. See the
hardware capability document for the tested revision and retained local evidence.
