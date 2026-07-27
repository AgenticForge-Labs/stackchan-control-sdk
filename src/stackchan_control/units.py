"""Conversions and limits for StackChan's native servo angle units."""

from __future__ import annotations

import math
from typing import Final

NATIVE_ANGLE_UNITS_PER_DEGREE: Final = 10

YAW_MIN_TENTHS: Final = -1280
YAW_MAX_TENTHS: Final = 1280
PITCH_MIN_TENTHS: Final = 30
PITCH_MAX_TENTHS: Final = 870


def degrees_to_native_angle(degrees: float) -> int:
    """Convert degrees to native tenths using half-away-from-zero rounding."""
    if not math.isfinite(degrees):
        raise ValueError("degrees must be finite")
    scaled = degrees * NATIVE_ANGLE_UNITS_PER_DEGREE
    return math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)


def native_angle_to_degrees(angle_tenths: int) -> float:
    """Convert M5Stack's integer tenths-of-a-degree representation to degrees."""
    return angle_tenths / NATIVE_ANGLE_UNITS_PER_DEGREE
