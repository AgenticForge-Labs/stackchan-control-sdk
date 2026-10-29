import math

import pytest

from stackchan_control.neohex import NeoHexFrame, light_show_frame
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


@pytest.mark.parametrize("name", ["rainbow", "comets", "sparkles"])
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
