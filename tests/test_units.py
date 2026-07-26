import math

import pytest

from stackchan_control import degrees_to_native_angle, native_angle_to_degrees


def test_degree_conversion() -> None:
    assert degrees_to_native_angle(45) == 450
    assert degrees_to_native_angle(-12.25) == -122
    assert native_angle_to_degrees(550) == 55.0


def test_degree_conversion_rejects_non_finite_values() -> None:
    for value in (math.inf, -math.inf, math.nan):
        with pytest.raises(ValueError, match="finite"):
            degrees_to_native_angle(value)
