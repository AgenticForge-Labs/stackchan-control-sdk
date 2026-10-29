from typing import Any

from stackchan_control.external_protocol import ExternalEvent
from stackchan_control.hardware_probe import run_probe


class FakeClient:
    port = "FAKE"

    def __init__(self, *, fail_state: bool = False) -> None:
        self.fail_state = fail_state
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 8.0,
    ) -> list[ExternalEvent]:
        del timeout
        self.calls.append((method, params))
        if self.fail_state and method == "system.state":
            raise RuntimeError("state unavailable")
        result: dict[str, Any] | None = None
        if method == "system.hello":
            result = {"native_angle_unit": "tenths_of_a_degree"}
        elif method == "system.state":
            feature = {"x": 0, "y": 0, "rotation": 0, "weight": 0, "size": 0}
            result = {
                "yaw_angle_tenths": 25,
                "pitch_angle_tenths": 440,
                "avatar": {
                    "leftEye": feature,
                    "rightEye": feature,
                    "mouth": feature,
                },
            }
        return [
            ExternalEvent(event="accepted", command_id="fake"),
            ExternalEvent(event="completed", command_id="fake", result=result),
        ]


def test_probe_uses_native_tenths(monkeypatch) -> None:
    monkeypatch.setattr("stackchan_control.hardware_probe.time.sleep", lambda _: None)
    client = FakeClient()

    report = run_probe(client, allow_motion=True, no_prompt=True)

    assert report["native_angle_unit"] == "tenths_of_a_degree"
    motions = [params for method, params in client.calls if method == "motion.update"]
    assert motions[0] == {
        "yawServo": {"angle": 0, "speed": 120},
        "pitchServo": {"angle": 450, "speed": 120},
    }
    commanded_yaw = [
        params["yawServo"]["angle"]
        for params in motions
        if params is not None and "yawServo" in params
    ]
    commanded_pitch = [
        params["pitchServo"]["angle"]
        for params in motions
        if params is not None and "pitchServo" in params
    ]
    assert -120 in commanded_yaw
    assert 120 in commanded_yaw
    assert 350 in commanded_pitch
    assert 550 in commanded_pitch
    assert motions[-1] == {
        "yawServo": {"angle": 25, "speed": 100},
        "pitchServo": {"angle": 440, "speed": 100},
    }


def test_probe_stops_when_initial_state_is_unavailable() -> None:
    client = FakeClient(fail_state=True)

    report = run_probe(client, allow_motion=True, no_prompt=True)

    assert report["tests"][-1]["name"] == "state_initial"
    assert report["tests"][-1]["command_status"] == "fail"
    assert not any(method == "motion.update" for method, _ in client.calls)


def test_motion_timeout_stops_without_restoration_or_later_commands(monkeypatch) -> None:
    monkeypatch.setattr("stackchan_control.hardware_probe.time.sleep", lambda _: None)

    class TimeoutClient(FakeClient):
        def request(self, method, params=None, *, timeout=8.0):
            if method == "motion.update":
                self.calls.append((method, params))
                raise TimeoutError("servo completion timed out")
            return super().request(method, params, timeout=timeout)

    client = TimeoutClient()
    report = run_probe(client, allow_motion=True, no_prompt=True)
    assert report["aborted"] is True
    assert [m for m, _ in client.calls].count("motion.update") == 1
    assert client.calls[-1][0] == "system.stop"
    assert report["tests"][-1]["name"] == "neutral_pose"
    assert report["tests"][-1]["command_status"] == "fail"


def test_negative_motion_observation_stops_probe(monkeypatch) -> None:
    monkeypatch.setattr("stackchan_control.hardware_probe.time.sleep", lambda _: None)
    monkeypatch.setattr(
        "stackchan_control.hardware_probe._observe",
        lambda prompt, **k: "fail" if "smoothly" in prompt else "pass",
    )
    client = FakeClient()
    report = run_probe(client, allow_motion=True, no_prompt=False)
    assert report["aborted"] is True
    assert [m for m, _ in client.calls].count("motion.update") == 1
    assert client.calls[-1][0] == "system.stop"


def test_failed_face_observation_prevents_motion(monkeypatch) -> None:
    monkeypatch.setattr("stackchan_control.hardware_probe.time.sleep", lambda _: None)
    monkeypatch.setattr("stackchan_control.hardware_probe._observe", lambda *a, **k: "fail")
    client = FakeClient()
    report = run_probe(client, allow_motion=True, no_prompt=False)
    assert report["aborted"] is True
    assert not any(m == "motion.update" for m, _ in client.calls)


def test_interrupt_during_motion_attempts_stop_and_retains_evidence(monkeypatch) -> None:
    monkeypatch.setattr("stackchan_control.hardware_probe.time.sleep", lambda _: None)

    class InterruptedClient(FakeClient):
        def request(self, method, params=None, *, timeout=8.0):
            if method == "motion.update":
                self.calls.append((method, params))
                raise KeyboardInterrupt
            if method == "system.stop":
                self.calls.append((method, params))
                raise RuntimeError("USB disconnected")
            return super().request(method, params, timeout=timeout)

    client = InterruptedClient()
    report = run_probe(client, allow_motion=True, no_prompt=True)
    assert report["aborted"] is True
    assert client.calls[-1][0] == "system.stop"
    assert [m for m, _ in client.calls].count("motion.update") == 1
    assert report["tests"][-1]["safety_stop_error"] == "USB disconnected"
    assert "Power off" in report["operator_action"]
