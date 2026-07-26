# Firmware extension

This directory contains an overlay for the public M5Stack StackChan ESP-IDF firmware. It does not duplicate the entire upstream repository. `upstream.lock.json` pins the exact upstream commit and `tools/prepare_firmware.py` creates a reproducible worktree.

## What the overlay adds

The **EXT CONTROL** launcher app:

- creates the existing `DefaultAvatar`
- opens the ESP32-S3 USB Serial/JTAG data channel
- accepts newline-delimited JSON commands prefixed with `@AF `
- routes avatar, motion, lighting, and animation data into existing M5Stack APIs
- reports accepted, completed, failed, state, and capability events
- stops active animation and holds the current servo angles on exit or `system.stop`

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

## Flash and restore

Do not flash until the retail device is available and its existing firmware version has been recorded. The first physical session should identify which StackChan/CoreS3 USB connector exposes the ESP32-S3 USB Serial/JTAG port.

Flash the prepared image with:

```bash
idf.py -p PORT flash monitor
```

Keep the upstream repository and M5Stack's official flashing instructions available so the factory firmware can be restored.

## Wire protocol

Host command:

```text
@AF {"id":"abc","method":"system.hello","params":{}}
```

Firmware event:

```text
@AF {"id":"abc","event":"accepted"}
@AF {"id":"abc","event":"completed","result":{"protocol_version":"1.0"}}
```

Normal ESP-IDF logs may share the same serial port. Host software ignores lines without the `@AF ` prefix.

See `docs/hardware-capability-test.md` for the exact plug-in test sequence.
