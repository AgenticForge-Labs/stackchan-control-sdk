"""Sequential host playback for validated native assets; no firmware animation."""

from __future__ import annotations

import time
from dataclasses import dataclass

from .assets import NativeAsset, validate_asset
from .external_control import BuiltinLights, ExternalControl
from .external_protocol import ExternalEvent
from .models import AvatarUpdate, MotionUpdate
from .routed_serial import RoutedSerialError


class PlaybackInterrupted(RoutedSerialError):
    """Playback was interrupted by a stop request; stop outcome is separate."""


@dataclass(frozen=True)
class StepResult:
    index: int
    requested_at_s: float
    started_at_s: float
    finished_at_s: float
    events: tuple[ExternalEvent, ...]


def play_asset(
    robot: ExternalControl,
    asset: NativeAsset,
    *,
    expected_revision: str,
    expected_generation: int | None = None,
) -> tuple[StepResult, ...]:
    """Run steps in order, delaying late steps; reject stale identities before submission.

    Stop invalidates remaining steps. Results report host monotonic timings and
    firmware events, not independent physical measurements. Device state and
    capabilities are rechecked by the facade for each operation.
    """
    validate_asset(asset)
    if asset.revision != expected_revision:
        raise ValueError("asset revision does not match expected revision")
    generation, stopped = robot._generation()
    if expected_generation is not None:
        if type(expected_generation) is not int or expected_generation < 0:
            raise ValueError("expected_generation must be a nonnegative integer")
        if expected_generation != generation:
            raise PlaybackInterrupted("playback preflight invalidated by stop")
    start = time.monotonic()
    results: list[StepResult] = []
    for index, step in enumerate(asset.steps):
        if stopped.wait(max(0.0, start + step.at_s - time.monotonic())):
            raise PlaybackInterrupted("stop requested during playback; check stop outcome")
        started = time.monotonic() - start
        if step.operation == "head" and isinstance(step.update, MotionUpdate):
            events = robot.move_head(step.update, expected_generation=generation)
        elif step.operation == "face" and isinstance(step.update, AvatarUpdate):
            events = robot.update_face(step.update, expected_generation=generation)
        elif step.operation == "lights" and isinstance(step.update, BuiltinLights):
            events = robot.update_lights(step.update, expected_generation=generation)
        else:
            raise ValueError("asset step operation and update do not match")
        if stopped.is_set():
            raise PlaybackInterrupted("stop requested during playback; check stop outcome")
        results.append(StepResult(index, step.at_s, started, time.monotonic() - start, events))
    return tuple(results)
