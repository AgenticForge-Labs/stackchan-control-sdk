import math

import pytest

from stackchan_control.neohex import NEOHEX_RADII, NeoHexFrame, light_show_frame
from stackchan_control.serial_client import SerialControlClient


@pytest.mark.parametrize("count", [0, 36, 38])
def test_wrong_pixel_count(count):
    with pytest.raises(ValueError):
        NeoHexFrame(("#ff0000",) * count)


@pytest.mark.parametrize("value", [-1, 33, 255, True, 8.5])
def test_brightness_is_bounded_integer(value):
    with pytest.raises(ValueError):
        NeoHexFrame.solid("#ff0000", value)


@pytest.mark.parametrize("value", ["red", "#gg0000", "#000", 123])
def test_invalid_colors(value):
    with pytest.raises(ValueError):
        NeoHexFrame.solid(value)


@pytest.mark.parametrize("name", ["rainbow", "comets", "sparkles", "radiate", "organic"])
def test_show_generates_valid_changing_frames(name):
    a = light_show_frame(name, 0)
    b = light_show_frame(name, 0.5)
    assert len(a.pixels) == 37
    assert a != b
    assert a.brightness == 8
    assert a == light_show_frame(name, 0)


@pytest.mark.parametrize("value", [-1, math.inf, math.nan])
def test_bad_show_time(value):
    with pytest.raises(ValueError):
        light_show_frame("rainbow", value)


def test_serial_frame_only_uses_external_lights_command(monkeypatch):
    calls = []
    client = SerialControlClient("FAKE")
    monkeypatch.setattr(
        client, "request", lambda method, params: calls.append((method, params)) or []
    )
    client.set_external_lights(NeoHexFrame.solid("#ff0080", 4))
    assert calls == [("external_lights.update", {"pixels": ["#ff0080"] * 37, "brightness": 4})]


def test_radial_layout_has_unique_center_and_six_nearest_neighbors():
    assert len(NEOHEX_RADII) == 37
    assert NEOHEX_RADII[18] == 0
    assert sum(r == 0 for r in NEOHEX_RADII) == 1
    assert sum(abs(r - 1) < 1e-9 for r in NEOHEX_RADII) == 6
    assert max(NEOHEX_RADII) == 3


def test_radiate_moves_from_center_outward_and_changes_color():
    start = light_show_frame("radiate", 0)
    neighbors = light_show_frame("radiate", 2.4 / 4.2)
    outer = light_show_frame("radiate", 3 * 2.4 / 4.2)
    repeated = light_show_frame("radiate", 2.4)
    assert start.pixels[18] != "#000000"
    assert all(c == "#000000" for i, c in enumerate(start.pixels) if i != 18)
    assert neighbors.pixels[18] == "#000000"
    assert all(
        neighbors.pixels[i] != "#000000" for i, r in enumerate(NEOHEX_RADII) if abs(r - 1) < 1e-9
    )
    assert all(outer.pixels[i] != "#000000" for i, r in enumerate(NEOHEX_RADII) if r == 3)
    assert repeated.pixels[18] != start.pixels[18]


def test_organic_wave_is_soft_and_faster_than_radiate():
    def energy(frame):
        return sum(int(c[j : j + 2], 16) for c in frame.pixels for j in (1, 3, 5))

    # Around one second the organic wave has reached the edge; the old wave has not.
    fast = light_show_frame("organic", 0.85)
    slow = light_show_frame("radiate", 0.85)
    outer = [i for i, r in enumerate(NEOHEX_RADII) if r == 3]
    assert sum(int(fast.pixels[i][1:], 16) for i in outer) > 0
    assert all(slow.pixels[i] == "#000000" for i in outer)
    # Gaussian falloff lights more than one radial band at intermediate strengths.
    levels = {max(int(c[j : j + 2], 16) for j in (1, 3, 5)) for c in fast.pixels}
    assert len(levels) > 3
    assert energy(fast) > 0
