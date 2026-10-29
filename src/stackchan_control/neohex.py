"""Native frames for one 37-pixel NeoHEX on StackChan Port A (GPIO 2)."""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass
from typing import Any

PIXEL_COUNT = 37
MAX_BRIGHTNESS = 32

# M5Stack's NeoHEX front PCB photograph shows serpentine rows of 4/5/6/7/6/5/4.
# LED 1 is at the top left; LED 37 is at the bottom right. Center is index 18.
# https://static-cdn.m5stack.com/resource/docs/products/unit/neohex/neohex_04.webp
NEOHEX_RADII = tuple(
    math.hypot(column - (length - 1) / 2, (row - 3) * math.sqrt(3) / 2)
    for row, length in enumerate((4, 5, 6, 7, 6, 5, 4))
    for column in (range(length) if row % 2 == 0 else reversed(range(length)))
)


@dataclass(frozen=True)
class NeoHexFrame:
    pixels: tuple[str, ...]
    brightness: int = 8

    def __post_init__(self) -> None:
        if len(self.pixels) != PIXEL_COUNT:
            raise ValueError("NeoHEX requires exactly 37 pixels")
        if type(self.brightness) is not int or not 0 <= self.brightness <= MAX_BRIGHTNESS:
            raise ValueError("brightness must be an integer 0..32")
        for color in self.pixels:
            if (
                not isinstance(color, str)
                or len(color) != 7
                or color[0] != "#"
                or any(c not in "0123456789abcdefABCDEF" for c in color[1:])
            ):
                raise ValueError("pixels must use #RRGGBB")

    @classmethod
    def solid(cls, color: str, brightness: int = 8) -> NeoHexFrame:
        return cls((color,) * PIXEL_COUNT, brightness)

    def to_dict(self) -> dict[str, Any]:
        return {"pixels": list(self.pixels), "brightness": self.brightness}


def light_show_frame(name: str, seconds: float, brightness: int = 8) -> NeoHexFrame:
    """Generate native colors; radiate uses the standard NeoHEX PCB layout."""
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("time must be finite and nonnegative")
    colors = []
    for i in range(PIXEL_COUNT):
        if name == "organic":
            # Positive but varying phase speed gives a living pulse without reversal.
            phase = seconds / 1.15 + 0.07 * math.sin(seconds * 0.9)
            radius = (phase % 1) * 4.2
            distance = NEOHEX_RADII[i]
            envelope = math.exp(-0.5 * ((distance - radius) / 0.55) ** 2)
            shimmer = 0.88 + 0.12 * math.sin(seconds * 2.1 + i * 0.7)
            value = envelope * shimmer
            hue = (seconds * 0.075 + distance * 0.06) % 1
        elif name == "radiate":
            radius = (seconds % 2.4) / 2.4 * 4.2
            distance = NEOHEX_RADII[i]
            value = max(0.0, 1 - abs(distance - radius) / 0.8) ** 1.5
            hue = (seconds * 0.12 + distance * 0.10) % 1
        elif name == "rainbow":
            hue, value = (i / PIXEL_COUNT + seconds * 0.12) % 1, 1.0
        elif name == "comets":
            head = seconds * 12 % PIXEL_COUNT
            trail = (head - i) % PIXEL_COUNT
            opposite = ((head + PIXEL_COUNT / 2) - i) % PIXEL_COUNT
            value = max(max(0.0, 1 - trail / 7), max(0.0, 1 - opposite / 7))
            hue = 0.52 if trail < opposite else 0.88
        elif name == "sparkles":
            value = max(0.0, math.sin(seconds * (2 + i % 5) + i * 2.39996)) ** 14
            hue = (0.55 + 0.3 * math.sin(i * 1.7 + seconds * 0.2)) % 1
        else:
            raise ValueError(f"unknown show: {name}")
        rgb = colorsys.hsv_to_rgb(hue, 0.85, value)
        colors.append("#" + "".join(f"{round(c * 255):02x}" for c in rgb))
    return NeoHexFrame(tuple(colors), brightness)
