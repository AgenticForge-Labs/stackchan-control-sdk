import json
import threading
from dataclasses import replace

import pytest

from stackchan_control.assets import AssetStep, load_asset
from stackchan_control.models import AvatarUpdate, FeatureUpdate
from stackchan_control.playback import PlaybackInterrupted, play_asset


class Robot:
    def __init__(self):
        self.generation = 0
        self.event = threading.Event()
        self.calls = []
        self.first_step = threading.Event()

    def _generation(self):
        return self.generation, self.event

    def update_face(self, update, *, expected_generation):
        if expected_generation != self.generation:
            raise RuntimeError("action invalidated by stop")
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


def test_replay_rejects_stale_public_generation_before_any_step(tmp_path):
    item = asset(tmp_path, at=0)
    robot = Robot()
    robot.generation += 1
    with pytest.raises(PlaybackInterrupted, match="preflight invalidated"):
        play_asset(robot, item, expected_revision=item.revision, expected_generation=0)
    assert robot.calls == []


def test_replay_rejects_invalid_generation_and_preserves_revision_check(tmp_path):
    item = asset(tmp_path, at=0)
    robot = Robot()
    with pytest.raises(ValueError, match="nonnegative integer"):
        play_asset(robot, item, expected_revision=item.revision, expected_generation=True)
    with pytest.raises(ValueError, match="revision"):
        play_asset(robot, item, expected_revision="stale", expected_generation=0)
    assert robot.calls == []


def test_stop_during_asset_validation_blocks_first_step(tmp_path, monkeypatch):
    import stackchan_control.playback as playback_module

    item = asset(tmp_path, at=0)
    robot = Robot()
    entered, release = threading.Event(), threading.Event()
    validate = playback_module.validate_asset
    errors = []

    def stalled_validate(asset_value):
        entered.set()
        assert release.wait(timeout=2)
        return validate(asset_value)

    monkeypatch.setattr(playback_module, "validate_asset", stalled_validate)

    def run():
        try:
            play_asset(robot, item, expected_revision=item.revision, expected_generation=0)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    assert entered.wait(timeout=2)
    # Simulate a firmware-confirmed STOP generation change during preflight.
    robot.generation += 1
    robot.event.set()
    release.set()
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], PlaybackInterrupted)
    assert robot.calls == []
