import threading
import time

import pytest
from test_external_control import Firmware

from stackchan_control.external_control import ExternalControl
from stackchan_control.lighting import LightingCleanupError, LightingInterrupted, sustain_neohex
from stackchan_control.neohex import NeoHexFrame
from stackchan_control.routed_serial import RoutedSerialClient, RoutedSerialError


@pytest.fixture
def lighting():
    firmware = Firmware()
    client = RoutedSerialClient(firmware)
    yield firmware, ExternalControl(client, timeout=0.5)
    client.close()


def frames(firmware):
    return [c["params"] for c in firmware.commands if c["method"] == "external_lights.update"]


def test_sustained_frame_refreshes_and_clears(lighting):
    firmware, robot = lighting
    result = sustain_neohex(robot, NeoHexFrame.solid("#ff0000"), duration_s=0.16)
    assert result.refreshes >= 2
    assert result.watchdog_ms == 120 and result.cleanup_completed
    sent = frames(firmware)
    assert len(sent) == result.refreshes + 1
    assert all(frame["brightness"] == 8 for frame in sent[:-1])
    assert sent[-1]["brightness"] == 0


def test_cancel_clears_and_stop_does_not_send_late_refresh(lighting):
    firmware, robot = lighting
    cancel = threading.Event()
    errors = []

    def run():
        try:
            sustain_neohex(robot, NeoHexFrame.solid("#ff0000"), duration_s=2, cancel=cancel)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    assert firmware.neohex_started.wait(1)
    cancel.set()
    thread.join(1)
    assert not thread.is_alive()
    assert isinstance(errors[0], LightingInterrupted)
    assert frames(firmware)[-1]["brightness"] == 0

    firmware.neohex_started.clear()
    errors.clear()
    cancel.clear()
    thread = threading.Thread(target=run)
    thread.start()
    assert firmware.neohex_started.wait(1)
    robot.stop()
    thread.join(1)
    assert not thread.is_alive()
    assert isinstance(errors[0], LightingInterrupted)
    methods = [c["method"] for c in firmware.commands]
    assert "external_lights.update" not in methods[methods.index("system.stop") + 1 :]


def test_failed_cleanup_is_not_reported_success(lighting):
    firmware, robot = lighting
    firmware.reject_neohex_off = True
    with pytest.raises(LightingCleanupError, match="cleanup unconfirmed"):
        sustain_neohex(robot, NeoHexFrame.solid("#ff0000"), duration_s=0.03)


def test_refresh_exceeding_watchdog_fails_and_clears(lighting, monkeypatch):
    firmware, robot = lighting
    original = robot._update_neohex

    def delayed(frame, generation):
        if frame.brightness:
            time.sleep(0.13)
        return original(frame, generation)

    monkeypatch.setattr(robot, "_update_neohex", delayed)
    with pytest.raises(RoutedSerialError, match="exceeded firmware watchdog"):
        sustain_neohex(robot, NeoHexFrame.solid("#ff0000"), duration_s=1)
    assert frames(firmware)[-1]["brightness"] == 0
