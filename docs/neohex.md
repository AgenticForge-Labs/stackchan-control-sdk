# External NeoHEX 37 LEDs

EXT CONTROL supports one M5Stack NeoHEX 37 WS2812 board on the head's side
Port A. A standard Grove cable connects black to ground, red to 5 V, yellow
(data) to GPIO 2, and white to an unused input on the NeoHEX. The two top
ports are B and C. Port A/GPIO 2 is reserved for the NeoHEX while this driver
is active; do not share it with an I2C peripheral.

The firmware uses Espressif's `led_strip` RMT driver (3.0.3 in the tested
resolved dependency lock), WS2812 timing, and GRB wire order. It initializes
lazily on the first valid external-light command and releases the peripheral
when EXT CONTROL closes. WS2812 has no discovery/acknowledgment channel:
capability reports describe the configured output, not detected board presence.

## USB command

`external_lights.update` takes exactly 37 `#RRGGBB` strings in `pixels`, plus
integer `brightness` from 0 to 32. The firmware scales each 0..255 color channel
by `brightness/255`. The host default is 8; start physical checks at 4.
The firmware independently enforces this conservative first-session brightness
ceiling. It is a channel scaling limit, not a measured current guarantee.

```python
from stackchan_control import NeoHexFrame
from stackchan_control.serial_client import SerialControlClient

with SerialControlClient("DETECTED_PORT") as client:
    client.set_external_lights(NeoHexFrame.solid("#ff0000", brightness=4))
    client.set_external_lights(NeoHexFrame.solid("#000000", brightness=0))
```

A valid command emits accepted and then completed only after the driver refresh
succeeds. Malformed frames fail before the driver is touched. Peripheral errors
return failed and are exposed in `system.state.external_lights.driver_error`.
`system.state` reports initialized, commanded_lit, and brightness; these describe
software state and do not independently verify physical illumination.

While EXT CONTROL is polling, 1.5 seconds without a valid new external frame
clears the board. Keep streaming frames to hold a static color longer. This is
an external-LED timeout, not a servo watchdog or a guarantee through firmware
failure. `system.stop` and app exit also clear external LEDs. The built-in RGB
commands remain separate.

## Shows

After the dim RGB check confirms wiring and color order:

```bash
python tools/neohex_show.py --port DETECTED_PORT --show all \
  --brightness 8 --seconds 6 --output hardware-reports/neohex-shows.json
```

Available shows are `rainbow`, `comets`, and `sparkles`. They stream at a target
20 frames/second and end with an all-off frame, including on interruption.
They use wire pixel indices; no geometric ring mapping is assumed. They send
no servo or face commands. `NeoHexFrame` and `light_show_frame()` are reusable
native SDK controls; higher-level character performance stays in Puppeteer.

## Checks

The Python suite validates pixel counts, hex colors, brightness bounds, frame
variation, and command routing. A C++ compiler is required for the test that
compiles the actual firmware driver against a fake LED peripheral and checks
scaling, timeout clearing (including after a failed refresh), and cleanup.
The ESP-IDF build checks the real peripheral API. Physical color, timeout, and
show observations must be recorded separately under `hardware-reports/`.

## First physical validation — 2026-10-28

Firmware/SDK `f50440d917331f2c7c6979966ebf5cc1b3c69a82` was built under
ESP-IDF 5.5.4 and flashed through body USB `/dev/ttyACM1`; all five image hashes
verified. One NeoHEX was connected to side Port A with a standard Grove cable.
The operator relaunched EXT CONTROL before checks.

- Firmware advertised extension 0.3.0 and `external_lights.update`.
- Wrong pixel count, invalid hex color, brightness 33, and boolean brightness
  were rejected. State confirmed these invalid requests did not initialize
  the LED peripheral.
- At brightness 4, the operator confirmed red, green, then blue on the external
  board, followed by lights-off when updates stopped. Two seconds after the
  last frame, state reported commanded_lit false, brightness 0, and ESP_OK.
  This validates observed timeout-off, not independently measured exact timing.
- At brightness 8, rainbow, comets, and sparkles were each streamed for six
  seconds. Every frame completed; the operator confirmed all three distinct
  animated patterns and final lights-off. The shows sent no face or servo commands.

Evidence remains local and ignored: `hardware-reports/neohex-build-identity.json`,
`neohex-first-check.json`, `neohex-shows.json`, and the `neohex-*` build/check logs.
The complete factory recovery backup remains preserved. Python checks passed:
46 tests (including the actual-driver C++ peripheral test), Ruff, and mypy.
No claim is made about full-brightness power capacity, additional boards,
physical ring/index mapping, or operation on other Grove ports.
