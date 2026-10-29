import json
import threading
from dataclasses import replace

import pytest

from stackchan_control.assets import AssetStep, load_asset
from stackchan_control.models import AvatarUpdate, FeatureUpdate
from stackchan_control.playback import PlaybackInterrupted, play_asset


class Robot:
    def __init__(self):
        self.event = threading.Event()
        self.calls = []
        self.first_step = threading.Event()

    def _generation(self):
        return 0, self.event

    def update_face(self, update, *, _generation):
        self.calls.append(update)
        self.first_step.set()
        return ()


def asset(tmp_path, at=0.5):
    path = tmp_path / "asset.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "face",
                "kind": "sequence",
                "steps": [
                    {"at_s": 0, "operation": "face", "parameters": {"mouth": {"size": 1}}},
                    {"at_s": at, "operation": "face", "parameters": {"mouth": {"size": 2}}},
                ],
            }
        )
    )
    return load_asset(path)


def test_playback_checks_revision_and_all_steps_before_first_action(tmp_path):
    item = asset(tmp_path)
    robot = Robot()
    with pytest.raises(ValueError, match="revision"):
        play_asset(robot, item, expected_revision="stale")
    bad = replace(
        item, steps=(item.steps[0], AssetStep(1, "head", AvatarUpdate(mouth=FeatureUpdate(size=1))))
    )
    with pytest.raises(ValueError, match="do not match"):
        play_asset(robot, bad, expected_revision=item.revision)
    assert robot.calls == []


def test_stop_interrupts_future_steps_without_claiming_stop_outcome(tmp_path):
    item = asset(tmp_path, at=2)
    robot = Robot()
    errors = []

    def run():
        try:
            play_asset(robot, item, expected_revision=item.revision)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    assert robot.first_step.wait(1)
    robot.event.set()
    thread.join(1)
    assert not thread.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], PlaybackInterrupted)
    assert len(robot.calls) == 1


def test_playback_returns_requested_and_observed_timing(tmp_path):
    item = asset(tmp_path, at=0)
    result = play_asset(Robot(), item, expected_revision=item.revision)
    assert len(result) == 2
    assert all(
        r.started_at_s >= r.requested_at_s and r.finished_at_s >= r.started_at_s for r in result
    )
