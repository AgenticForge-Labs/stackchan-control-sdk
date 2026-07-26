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
