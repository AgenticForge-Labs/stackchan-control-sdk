import json
import queue
import threading

import pytest

from stackchan_control.external_control import BuiltinLights, ExternalControl, FirmwareRejected
from stackchan_control.models import AvatarUpdate, FeatureUpdate, MotionUpdate, ServoUpdate
from stackchan_control.neohex import NeoHexFrame
from stackchan_control.routed_serial import RoutedSerialClient, RoutedSerialError, UnknownOutcome


class Firmware:
    def __init__(self):
        self.queue = queue.Queue()
        self.commands = []
        self.motion_id = None
        self.reject = None
        self.capabilities = [
            "avatar.update",
            "motion.update.position_only",
            "lights.update",
            "external_lights.update",
            "system.state",
            "system.stop",
        ]
        self.state_started = threading.Event()
        self.state_release = threading.Event()
        self.pause_state = False
        self.watchdog_ms = 120
        self.neohex_started = threading.Event()
        self.reject_neohex_off = False

    def emit(self, ident, event, **kwargs):
        self.queue.put(
            ("@AF " + json.dumps({"id": ident, "event": event, **kwargs}) + "\n").encode()
        )

    def write(self, data):
        command = json.loads(data.decode()[4:])
        self.commands.append(command)
        ident, method = command["id"], command["method"]
        if method == self.reject:
            self.emit(ident, "failed", detail="rejected")
        elif method == "system.capabilities":
            self.emit(
                ident,
                "completed",
                result={
                    "protocol_version": "1.0",
                    "capabilities": self.capabilities,
                    "external_lights": {"watchdog_ms": self.watchdog_ms},
                },
            )
        elif method == "external_lights.update":
            self.neohex_started.set()
            if self.reject_neohex_off and command["params"]["brightness"] == 0:
                self.emit(ident, "failed", detail="clear failed")
            else:
                self.emit(ident, "completed")
        elif method == "system.state":
            if self.pause_state:
                self.state_started.set()
            else:
                self.emit(
                    ident,
                    "completed",
                    result={"native_angle_limits_tenths": {"yaw": [-500, 500], "pitch": [30, 870]}},
                )
        elif method == "motion.update":
            self.motion_id = ident
            self.emit(ident, "accepted")
        elif method == "system.stop":
            if self.motion_id:
                self.emit(self.motion_id, "cancelled")
            self.emit(ident, "completed")
        else:
            self.emit(ident, "completed")
        return len(data)

    def flush(self):
        pass

    def readline(self):
        try:
            return self.queue.get(timeout=0.01)
        except queue.Empty:
            return b""

    def close(self):
        pass

    def release_state(self):
        command = next(c for c in reversed(self.commands) if c["method"] == "system.state")
        self.emit(
            command["id"],
            "completed",
            result={"native_angle_limits_tenths": {"yaw": [-500, 500], "pitch": [30, 870]}},
        )


@pytest.fixture
def setup():
    firmware = Firmware()
    client = RoutedSerialClient(firmware)
    yield firmware, ExternalControl(client, timeout=0.5)
    client.close()


def test_face_is_typed_and_cannot_include_motion(setup):
    firmware, robot = setup
    robot.update_face(AvatarUpdate(mouth=FeatureUpdate(size=10)))
    assert firmware.commands[-1]["method"] == "avatar.update"
    assert firmware.commands[-1]["params"] == {"mouth": {"size": 10}}
    with pytest.raises(ValueError):
        robot.update_face(AvatarUpdate(mouth=FeatureUpdate(size=True)))
    assert not any(c["method"] == "motion.update" for c in firmware.commands)


def test_capabilities_and_firmware_limits_fail_closed(setup):
    firmware, robot = setup
    firmware.capabilities.remove("avatar.update")
    with pytest.raises(RoutedSerialError, match="does not advertise"):
        robot.update_face(AvatarUpdate(mouth=FeatureUpdate(size=1)))
    with pytest.raises(ValueError, match="reported motion limits"):
        robot.move_head(MotionUpdate(yaw=ServoUpdate(angle=600, speed=10)))
    assert not any(c["method"] == "motion.update" for c in firmware.commands)


def test_stop_interrupts_motion_and_rejection_is_not_success(setup):
    firmware, robot = setup
    errors = []

    def move():
        try:
            robot.move_head(MotionUpdate(yaw=ServoUpdate(angle=10, speed=10)))
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=move)
    thread.start()
    # The motion command's accepted event may be in flight; wait for submission.
    for _ in range(1000):
        if firmware.motion_id:
            break
        threading.Event().wait(0.001)
    assert firmware.motion_id
    robot.stop()
    thread.join(1)
    assert not thread.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], FirmwareRejected)
    assert errors[0].event.event == "cancelled"
    firmware.reject = "lights.update"
    with pytest.raises(FirmwareRejected):
        robot.update_lights(BuiltinLights(left_color="#000000"))


def test_stop_invalidates_motion_preflight(setup):
    firmware, robot = setup
    firmware.pause_state = True
    errors = []

    def move():
        try:
            robot.move_head(MotionUpdate(yaw=ServoUpdate(angle=10, speed=10)))
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=move)
    thread.start()
    assert firmware.state_started.wait(1)
    robot.stop()
    firmware.release_state()
    thread.join(1)
    assert not thread.is_alive()
    assert len(errors) == 1 and "invalidated by stop" in str(errors[0])
    assert not any(c["method"] == "motion.update" for c in firmware.commands)


def test_timed_out_motion_blocks_new_motion(setup):
    firmware, robot = setup
    with pytest.raises(UnknownOutcome):
        robot.move_head(MotionUpdate(yaw=ServoUpdate(angle=10, speed=10)))
    with pytest.raises(RoutedSerialError, match="outcome unknown"):
        robot.move_head(MotionUpdate(yaw=ServoUpdate(angle=20, speed=10)))
    assert sum(c["method"] == "motion.update" for c in firmware.commands) == 1


def test_failed_stop_inhibits_later_motion(setup):
    firmware, robot = setup
    firmware.reject = "system.stop"
    with pytest.raises(FirmwareRejected):
        robot.stop()
    with pytest.raises(RoutedSerialError, match="stop is pending or unconfirmed"):
        robot.move_head(MotionUpdate(yaw=ServoUpdate(angle=10, speed=10)))
    assert not any(c["method"] == "motion.update" for c in firmware.commands)


def test_public_execution_state_is_immutable_and_stale_actions_never_dispatch(setup):
    from dataclasses import FrozenInstanceError

    firmware, robot = setup
    token = robot.execution_state()
    assert token.generation == 0
    with pytest.raises(FrozenInstanceError):
        token.generation = 99
    robot.stop()
    assert robot.execution_state().generation == token.generation + 1

    attempts = (
        lambda: robot.update_face(
            AvatarUpdate(mouth=FeatureUpdate(size=1)),
            expected_generation=token.generation,
        ),
        lambda: robot.update_lights(
            BuiltinLights(left_color="#101010"),
            expected_generation=token.generation,
        ),
        lambda: robot.update_neohex(
            NeoHexFrame.solid("#000000", 3),
            expected_generation=token.generation,
        ),
        lambda: robot.move_head(
            MotionUpdate(yaw=ServoUpdate(angle=10, speed=10)),
            expected_generation=token.generation,
        ),
    )
    for attempt in attempts:
        with pytest.raises(RoutedSerialError, match="invalidated by stop"):
            attempt()
    actions = {c["method"] for c in firmware.commands}
    assert actions.isdisjoint({
        "avatar.update", "lights.update", "external_lights.update", "motion.update",
    })


def test_public_generation_rejects_invalid_values_and_conflicting_legacy_keyword(setup):
    _firmware, robot = setup
    update = AvatarUpdate(mouth=FeatureUpdate(size=1))
    for invalid in (True, -1, 1.2, "0"):
        with pytest.raises(ValueError, match="nonnegative integer"):
            robot.update_face(update, expected_generation=invalid)
    with pytest.raises(ValueError, match="only expected_generation"):
        robot.update_face(update, expected_generation=0, _generation=0)


def test_stop_while_neohex_capability_preflight_invalidates_frame(setup, monkeypatch):
    firmware, robot = setup
    before = robot.execution_state().generation
    started, proceed = threading.Event(), threading.Event()
    require = robot._require
    errors = []

    def stalled_require(capability):
        if capability == "external_lights.update":
            started.set()
            assert proceed.wait(timeout=2)
        return require(capability)

    monkeypatch.setattr(robot, "_require", stalled_require)

    def send_frame():
        try:
            robot.update_neohex(
                NeoHexFrame.solid("#110000", 1),
                expected_generation=before,
            )
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=send_frame)
    worker.start()
    assert started.wait(timeout=2)
    robot.stop()
    proceed.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], RoutedSerialError)
    assert "invalidated by stop" in str(errors[0])
    assert not any(c["method"] == "external_lights.update" for c in firmware.commands)


def test_unconfirmed_stop_inhibits_snapshot_and_neohex(setup):
    firmware, robot = setup
    token = robot.execution_state()
    firmware.reject = "system.stop"
    with pytest.raises(FirmwareRejected):
        robot.stop()
    with pytest.raises(RoutedSerialError, match="unconfirmed"):
        robot.execution_state()
    with pytest.raises(RoutedSerialError, match="invalidated by stop"):
        robot.update_neohex(
            NeoHexFrame.solid("#000000"), expected_generation=token.generation
        )
    assert not any(c["method"] == "external_lights.update" for c in firmware.commands)


def test_valid_generation_preserves_manual_and_legacy_clients(setup):
    from stackchan_control import ExecutionState as PublicExecutionState

    firmware, robot = setup
    token = robot.execution_state()
    assert isinstance(token, PublicExecutionState)
    robot.update_face(
        AvatarUpdate(mouth=FeatureUpdate(size=4)),
        expected_generation=token.generation,
    )
    robot.update_lights(
        BuiltinLights(left_color="#123456"),
        expected_generation=token.generation,
    )
    robot.update_neohex(
        NeoHexFrame.solid("#001100", 3),
        expected_generation=token.generation,
    )
    # Existing Puppeteer PR #7 still uses the SDK's private keyword.
    # Keep that implementation operational until its adapter migration.
    robot.update_face(
        AvatarUpdate(mouth=FeatureUpdate(size=5)),
        _generation=token.generation,
    )
    assert [
        c["method"] for c in firmware.commands
        if c["method"] in {"avatar.update", "lights.update", "external_lights.update"}
    ] == [
        "avatar.update", "lights.update", "external_lights.update", "avatar.update",
    ]
