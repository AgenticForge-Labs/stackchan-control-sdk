"""Bounded sustained NeoHEX output over the external-control transport."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from .external_control import ExternalControl
from .neohex import NeoHexFrame
from .routed_serial import RoutedSerialError


class LightingInterrupted(RoutedSerialError):
    """Lighting was interrupted; the caller must inspect the stop outcome."""


class LightingCleanupError(RoutedSerialError):
    """The off command failed or was unconfirmed; illumination is unknown."""

    def __init__(self, original: BaseException | None, cleanup: BaseException) -> None:
        self.original = original
        self.cleanup = cleanup
        super().__init__(f"NeoHEX cleanup unconfirmed: {cleanup}")


@dataclass(frozen=True)
class LightingResult:
    refreshes: int
    watchdog_ms: int
    cleanup_completed: bool


def sustain_neohex(
    robot: ExternalControl,
    frame: NeoHexFrame,
    *,
    duration_s: float,
    cancel: threading.Event | None = None,
) -> LightingResult:
    """Refresh a frame within the advertised watchdog and explicitly clear it.

    Cancellation by the supplied event clears the frame. A concurrent device stop
    invalidates refreshes and performs its own clear; its outcome is separate.
    A failed refresh or unconfirmed clear is never reported as success.
    """
    if isinstance(duration_s, bool) or not isinstance(duration_s, (int, float)):
        raise ValueError("duration_s must be a finite number in (0, 300]")
    if not math.isfinite(duration_s) or not 0 < duration_s <= 300:
        raise ValueError("duration_s must be a finite number in (0, 300]")
    frame = NeoHexFrame(tuple(frame.pixels), frame.brightness)
    if not robot._neohex_lock.acquire(blocking=False):
        raise RoutedSerialError("NeoHEX is busy")
    try:
        generation, stopped = robot._generation()
        info = robot.discover()
        external = info.get("external_lights")
        if "external_lights.update" not in info["capabilities"] or not isinstance(external, dict):
            raise RoutedSerialError("firmware did not advertise NeoHEX watchdog")
        watchdog_ms = external.get("watchdog_ms")
        if type(watchdog_ms) is not int or not 60 <= watchdog_ms <= 60000:
            raise RoutedSerialError("invalid NeoHEX watchdog")
        watchdog_s = watchdog_ms / 1000
        interval = min(watchdog_s / 3, 0.5)
        end = time.monotonic() + duration_s
        refreshes = 0
        previous_sent: float | None = None
        original: BaseException | None = None
        attempted = False
        try:
            while True:
                if stopped.is_set():
                    raise LightingInterrupted("stop requested; inspect stop outcome separately")
                if cancel is not None and cancel.is_set():
                    raise LightingInterrupted("NeoHEX lighting cancelled")
                sent_at = time.monotonic()
                if sent_at >= end:
                    break
                if previous_sent is not None and sent_at - previous_sent >= watchdog_s:
                    raise RoutedSerialError("NeoHEX refresh interval exceeded firmware watchdog")
                attempted = True
                robot._update_neohex(frame, generation)
                refreshes += 1
                previous_sent = sent_at
                if time.monotonic() - sent_at >= watchdog_s:
                    raise RoutedSerialError("NeoHEX refresh exceeded firmware watchdog")
                wake = min(end, sent_at + interval)
                while time.monotonic() < wake:
                    if stopped.wait(min(0.05, wake - time.monotonic())):
                        raise LightingInterrupted("stop requested; inspect stop outcome separately")
                    if cancel is not None and cancel.is_set():
                        raise LightingInterrupted("NeoHEX lighting cancelled")
        except BaseException as exc:
            original = exc
        if attempted and not stopped.is_set():
            try:
                robot._update_neohex(NeoHexFrame.solid("#000000", brightness=0), generation)
            except BaseException as exc:
                raise LightingCleanupError(original, exc) from exc
        if original is not None:
            raise original
        if stopped.is_set():
            raise LightingInterrupted("stop requested; inspect stop outcome separately")
        if not attempted:
            raise RoutedSerialError("NeoHEX duration elapsed before the first frame")
        return LightingResult(refreshes, watchdog_ms, cleanup_completed=attempted)
    finally:
        robot._neohex_lock.release()
