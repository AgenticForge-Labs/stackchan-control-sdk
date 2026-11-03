# Recovering a missing StackChan control app

Status: source-grounded, **non-moving operator checklist**. This is not an
automatic recovery service or permission to flash. Physical state and firmware
identity must be established on the actual robot. The official ESP-NOW
**Remote Control** app and AgenticForge **EXT CONTROL** app are different.

## Why an icon can disappear without a flash

At the pinned upstream M5Stack StackChan revision in
`firmware/upstream.lock.json`, `firmware/main/main.cpp` installs
`AppEspnowControl` (the stock wireless Remote Control) with the ordinary
launcher apps. Our `tools/prepare_firmware.py` adds
`AppExternalControl` (EXT CONTROL) to that *same* launcher. Both should
appear when this custom image actually runs the normal launcher.

However, the pinned firmware also checks
`XiaozhiConfig.startAiAgentOnBoot`. When enabled at cold boot, it can
**skip the whole Mooncake launcher** and start Xiaozhi directly. Opening the
stock AI Agent app also explicitly requests Xiaozhi startup, uninstalls the
launcher apps for that running session and enters Xiaozhi. An icon not
visible **inside that mode** does not prove that it was erased.

Separately, M5Stack's official StackChan product documentation says entering
AI Agent may check for and automatically install an online firmware update.
The Setup firmware-update action and App Center also contain firmware
download/launch paths in the pinned upstream source. A subsequent factory
firmware installation **can replace our custom EXT CONTROL app**. The
disappearance alone does not reveal whether any such update happened.

- Official documentation: https://docs.m5stack.com/en/StackChan/
- Pinned upstream: https://github.com/m5stack/StackChan
- Source anchors:
  `firmware/main/main.cpp`,
  `firmware/main/apps/app_ai_agent/app_ai_agent.cpp`,
  `firmware/main/apps/app_setup/workers/ai_agent.cpp`,
  `firmware/main/apps/app_setup/workers/about.cpp`,
  `firmware/main/apps/app_app_center/app_app_center.cpp`.

Do not disable arbitrary firmware updater logic or silently turn off other
factory functions. The owner must explicitly decide whether to use stock AI
Agent and online firmware updates or retain the custom USB-control image.

## Read-only triage, before ANY installation

1. **Stop competing owners.** Close the Pollen/M5Stack AI Agent and any
   concurrent USB client before testing the AgenticForge port. Do not run a
   second Puppeteer MCP process against an active Conversationalist ensemble.
   Avoid motion while Reachy or StackChan has an unknown action/STOP state.
2. **Identify which screen is actually running.** If the screen is in
   Xiaozhi/AI Agent conversation mode, first return to the ordinary
   launcher using documented on-device navigation, if available. A normal
   return/home or power cycle is different from a flash or factory reset.
   If AI Agent automatically starts again, note the setting; do not assume
   an image replacement. In the normal Setup UI, review the
   **Start AI Agent on boot** toggle. Avoid changing calibration, accounts,
   or factory settings just to discover the launcher.
3. **Name the missing app precisely.** The official **Remote Control** icon
   uses ESP-NOW wireless control; the custom **EXT CONTROL** icon is our USB
   `@AF` protocol. Stock firmware may show Remote Control but cannot show
   the custom EXT CONTROL entry. Scroll the full ordinary launcher before
   treating an icon as missing.
4. **Inspect the USB identity without commanding movement.** Use the
   previously tested body USB data port, or enumerate connected ports:

   ```bash
   cd ~/code/stackchan-control-sdk
   stackchan-probe ports
   ```

   Choose the operator-confirmed Espressif USB Serial/JTAG port, not an
   unrelated USB serial adapter. Do not blindly assume it is
   `/dev/ttyACM0` or `/dev/ttyACM1` on this boot.
5. **Only with EXT CONTROL open and no competing owner**, try the native
   non-motion hello handshake:

   ```bash
   stackchan-probe hello --port OPERATOR_CONFIRMED_PORT
   ```

   Retain the exact response: protocol, overlay/extension version,
   upstream version and board identity. A successful `@AF` hello proves
   that some EXT CONTROL firmware and the correct USB interface are active,
   **not** 0.4.0 support, physically safe motion, or motor settling.
   Missing USB transport or a failed hello does not by itself establish a
   firmware overwrite: the app may be closed, the port may be wrong, or
   the device may be in another service/boot mode.
6. **Check installed-image evidence without changing flash.** Record a
   photo of the ordinary launcher and the device's reported version.
   Preserve serial logs and any firmware/backup hashes privately. Compare
   with the retained local 2026-10-28 factory backup and first custom-image
   manifest described in `docs/hardware-capability-test.md`.
   Do not upload the 16 MiB factory backup, NVS, account pairing data,
   tokens or device-specific calibration to a public repository.

## If EXT CONTROL is actually absent

- First establish the exact current image and review the official M5Stack
  recovery method and original backup. The old overlay (0.3.0) can still
  control supported head/face/light operations if it remains installed; it
  cannot advertise the new `display.face_scale` 100/170% capability.
- A clean custom **0.4.0** firmware build and the offline-verified manual
  flash bundle are available from the connected GitHub workflow for the
  reviewed SDK source. See `docs/firmware-release.md`; verify every
  `SHA256SUMS` line, flash layout, flash/NVS boundaries and operator port
  before any actual installation.
- Installation is **attended and deliberate**, with physical access,
  recovery image, current calibration/settings records, backup, and
  unplug/power-control procedure. Never erase NVS or blindly reset factory
  settings as a shortcut. If the screen stays blank after a successful
  manual flash, check serial boot messages first. The earlier retail session
  was left in `waiting for download` until a brief release of RST; another
  flash was not necessary. Holding RST deliberately enters download mode.
- After a deliberate flash, launch EXT CONTROL, perform the read-only
  handshake and inspect `system.capabilities`; perform the documented
  staged, nonmoving face test before considering any movement. Record new
  visual evidence for both 100% and 170% presentation. Do not assume that
  a successful flash or firmware command completion proves physical STOP.
- Entering factory AI Agent or firmware-update UI later can replace the
  custom image again. We should not treat it as a compatible concurrent
  motion owner; maintain a *deliberate* decision between custom local
  control and stock hosted mode until the update/recovery process is
  independently qualified.

## Remaining engineering work

- Confirm whether the stock firmware's auto-update in current retail
  revisions follows exactly the pinned public source; M5Stack warns that
  released firmware can be newer than the source repository.
- Preserve verified offline images and complete build/source provenance.
  The custom build is not yet proven fully bit-reproducible.
- Only after an attended observation demonstrates which mode overwrote
  which image should we consider a product-level update/boot-mode policy.
  No bypass of vendor OTA safeguards, flash writes or NVS mutation has been
  implemented here.
