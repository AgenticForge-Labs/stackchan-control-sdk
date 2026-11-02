"""Typed, explicitly connected facade for the USB external-control firmware."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .capabilities import SCHEMA_VERSION, capability_schema
from .external_protocol import ExternalEvent
from .models import AvatarUpdate, MotionUpdate
from .neohex import NeoHexFrame
from .routed_serial import RoutedSerialClient, RoutedSerialError


@dataclass(frozen=True)
class NativeCapability:
    id: str
    method: str
    effect: str
    resources: tuple[str, ...]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "method": self.method,
            "effect": self.effect,
            "resources": list(self.resources),
            "description": self.description,
            "schema_version": SCHEMA_VERSION,
            "parameters_schema": capability_schema(self.id),
        }


# Static host support is intersected with the connected firmware's response.
CAPABILITIES = MappingProxyType(
    {
        item.id: item
        for item in (
            NativeCapability(
                "avatar.update", "avatar.update", "visual", ("face",), "Eye/mouth features"
            ),
            NativeCapability(
                "motion.update.position_only",
                "motion.update",
                "motion",
                ("head.pose",),
                "Yaw and pitch position",
            ),
            NativeCapability(
                "lights.update",
                "lights.update",
                "light",
                ("lights.builtin",),
                "Built-in RGB lights",
            ),
            NativeCapability(
                "external_lights.update",
                "external_lights.update",
                "light",
                ("lights.neohex",),
                "NeoHEX frame",
            ),
            NativeCapability("system.state", "system.state", "read", (), "Reported model state"),
            NativeCapability(
                "system.stop", "system.stop", "stop", (), "Stop motion and clear NeoHEX"
            ),
        )
    }
)


@dataclass(frozen=True, slots=True)
class ExecutionState:
    """Host STOP generation snapshot, not measured physical safety evidence."""

    generation: int


class FirmwareRejected(RoutedSerialError):
    def __init__(self, command_id: str, event: ExternalEvent) -> None:
        self.command_id = command_id
        self.event = event
        super().__init__(f"{event.event}: {event.detail or 'firmware rejected command'}")


@dataclass(frozen=True)
class BuiltinLights:
    left_color: str | None = None
    right_color: str | None = None
    left_duration: float | None = None
    right_duration: float | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, color in (("leftRgbColor", self.left_color), ("rightRgbColor", self.right_color)):
            if color is not None:
                if (
                    not isinstance(color, str)
                    or len(color) != 7
                    or color[0] != "#"
                    or any(c not in "0123456789abcdefABCDEF" for c in color[1:])
                ):
                    raise ValueError(f"{key} must use #RRGGBB")
                result[key] = color
        for key, duration in (
            ("leftRgbDuration", self.left_duration),
            ("rightRgbDuration", self.right_duration),
        ):
            if duration is not None:
                if (
                    isinstance(duration, bool)
                    or not isinstance(duration, (float, int))
                    or not math.isfinite(duration)
                    or not 0 <= duration <= 10
                ):
                    raise ValueError(f"{key} must be finite and within 0..10 seconds")
                result[key] = duration
        if not result:
            raise ValueError("lights update is empty")
        return result


class ExternalControl:
    """USB-only controls; connection and shutdown are explicit caller responsibilities."""

    def __init__(self, client: RoutedSerialClient, *, timeout: float = 8.0) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        self.client = client
        self.timeout = timeout
        self._motion_lock = threading.Lock()
        self._motion_id: str | None = None
        self._preparing_motion = False
        self._stop_generation = 0
        self._stop_in_progress = False
        self._stop_failed = False
        self._stop_event = threading.Event()
        self._neohex_lock = threading.Lock()

    def execution_state(self) -> ExecutionState:
        """Return a public STOP-generation token for later validated dispatch.

        Refuses while a STOP is pending or its outcome unconfirmed. A returned
        token is not a hardware lease, motion grant or proof of physical safety.
        """
        return ExecutionState(self._generation()[0])

    @staticmethod
    def _select_generation(
        expected_generation: int | None, legacy_generation: int | None
    ) -> int | None:
        # _generation is the legacy internal keyword used by existing SDK
        # playback and Puppet adapters. Only one token may be supplied.
        if expected_generation is not None and legacy_generation is not None:
            raise ValueError("specify only expected_generation")
        selected = expected_generation if expected_generation is not None else legacy_generation
        if selected is not None and (type(selected) is not int or selected < 0):
            raise ValueError("expected_generation must be a nonnegative integer")
        return selected

    def _generation(self) -> tuple[int, threading.Event]:
        with self._motion_lock:
            if self._stop_in_progress or self._stop_failed:
                raise RoutedSerialError("stop is pending or unconfirmed; action is inhibited")
            return self._stop_generation, self._stop_event

    def _guarded_request(
        self, method: str, payload: dict[str, Any], generation: int
    ) -> tuple[ExternalEvent, ...]:
        with self._motion_lock:
            if generation != self._stop_generation or self._stop_in_progress or self._stop_failed:
                raise RoutedSerialError("action invalidated by stop")
            ident = self.client.submit(method, payload)
        return self._wait(ident)

    def _request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> tuple[ExternalEvent, ...]:
        ident = self.client.submit(method, params)
        return self._wait(ident)

    def _wait(self, ident: str) -> tuple[ExternalEvent, ...]:
        events = self.client.wait(ident, timeout=self.timeout)
        terminal = events[-1]
        if terminal.event != "completed":
            raise FirmwareRejected(ident, terminal)
        return events

    def discover(self) -> dict[str, Any]:
        result = self._request("system.capabilities")[-1].result
        if not isinstance(result, dict) or not isinstance(result.get("capabilities"), list):
            raise RoutedSerialError("invalid firmware capabilities response")
        if result.get("protocol_version") != "1.0" or any(
            not isinstance(item, str) for item in result["capabilities"]
        ):
            raise RoutedSerialError("unsupported or malformed firmware capabilities")
        return result

    def available_controls(self) -> tuple[NativeCapability, ...]:
        advertised = self.discover()["capabilities"]
        return tuple(CAPABILITIES[key] for key in sorted(CAPABILITIES) if key in advertised)

    def _require(self, capability: str) -> None:
        if capability not in self.discover()["capabilities"]:
            raise RoutedSerialError(f"firmware does not advertise {capability}")

    def state(self) -> dict[str, Any]:
        self._require("system.state")
        result = self._request("system.state")[-1].result
        if not isinstance(result, dict):
            raise RoutedSerialError("invalid firmware state response")
        return result

    def update_face(
        self,
        update: AvatarUpdate,
        *,
        expected_generation: int | None = None,
        _generation: int | None = None,
    ) -> tuple[ExternalEvent, ...]:
        payload = update.to_dict()
        if not payload or any(not feature for feature in payload.values()):
            raise ValueError("face update must contain nonempty features")
        for feature in payload.values():
            if any(type(value) is not int for value in feature.values()):
                raise ValueError("face feature values must be integers")
        selected = self._select_generation(expected_generation, _generation)
        generation = self._generation()[0] if selected is None else selected
        self._require("avatar.update")
        return self._guarded_request("avatar.update", payload, generation)

    def update_lights(
        self,
        update: BuiltinLights,
        *,
        expected_generation: int | None = None,
        _generation: int | None = None,
    ) -> tuple[ExternalEvent, ...]:
        payload = update.to_dict()
        selected = self._select_generation(expected_generation, _generation)
        generation = self._generation()[0] if selected is None else selected
        self._require("lights.update")
        return self._guarded_request("lights.update", payload, generation)

    def update_neohex(
        self, frame: NeoHexFrame, *, expected_generation: int | None = None
    ) -> tuple[ExternalEvent, ...]:
        selected = self._select_generation(expected_generation, None)
        if not self._neohex_lock.acquire(blocking=False):
            raise RoutedSerialError("NeoHEX is busy")
        try:
            generation = self._generation()[0] if selected is None else selected
            return self._update_neohex(frame, generation)
        finally:
            self._neohex_lock.release()

    def _update_neohex(self, frame: NeoHexFrame, generation: int) -> tuple[ExternalEvent, ...]:
        frame = NeoHexFrame(tuple(frame.pixels), frame.brightness)
        self._require("external_lights.update")
        return self._guarded_request("external_lights.update", frame.to_dict(), generation)

    def move_head(
        self,
        update: MotionUpdate,
        *,
        expected_generation: int | None = None,
        _generation: int | None = None,
    ) -> tuple[ExternalEvent, ...]:
        payload = update.to_dict()
        if not payload:
            raise ValueError("motion update is empty")
        for name, servo in (("yawServo", update.yaw), ("pitchServo", update.pitch)):
            if servo is None:
                continue
            if (
                not servo.is_complete_position()
                or type(servo.angle) is not int
                or type(servo.speed) is not int
            ):
                raise ValueError(f"{name} requires integer angle and speed only")
            low, high = (-1280, 1280) if name == "yawServo" else (30, 870)
            if not low <= servo.angle <= high or not 0 <= servo.speed <= 1000:
                raise ValueError(f"{name} exceeds protocol limits")
        selected = self._select_generation(expected_generation, _generation)
        with self._motion_lock:
            if self._stop_in_progress or self._stop_failed:
                raise RoutedSerialError("stop is pending or unconfirmed; motion is inhibited")
            if selected is not None and selected != self._stop_generation:
                raise RoutedSerialError("action invalidated by stop")
            if self._preparing_motion:
                raise RoutedSerialError("another motion is being prepared")
            if self._motion_id is not None:
                events = self.client.events(self._motion_id)
                if not events or events[-1].event not in {"completed", "failed", "cancelled"}:
                    raise RoutedSerialError("previous motion is pending or outcome unknown")
                self._motion_id = None
            self._preparing_motion = True
            generation = self._stop_generation
        try:
            self._require("motion.update.position_only")
            state = self.state()
            limits = state.get("native_angle_limits_tenths")
            if not isinstance(limits, dict):
                raise RoutedSerialError("firmware did not report motion limits")
            for axis, servo in (("yaw", update.yaw), ("pitch", update.pitch)):
                if servo is None:
                    continue
                bounds = limits.get(axis)
                if (
                    not isinstance(bounds, list)
                    or len(bounds) != 2
                    or any(type(value) is not int for value in bounds)
                    or bounds[0] > bounds[1]
                ):
                    raise RoutedSerialError(f"invalid {axis} motion limits")
                assert servo.angle is not None
                if not bounds[0] <= servo.angle <= bounds[1]:
                    raise ValueError(f"{axis} exceeds reported motion limits")
            with self._motion_lock:
                if generation != self._stop_generation:
                    raise RoutedSerialError("motion preflight invalidated by stop")
                self._motion_id = self.client.submit("motion.update", payload)
                ident = self._motion_id
        finally:
            with self._motion_lock:
                self._preparing_motion = False
        return self._wait(ident)

    def stop(self) -> tuple[ExternalEvent, ...]:
        # Invalidate preflight before sending; do not wait for motion completion.
        with self._motion_lock:
            self._stop_generation += 1
            self._stop_event.set()
            self._stop_event = threading.Event()
            if self._stop_in_progress:
                raise RoutedSerialError("stop is already in progress")
            self._stop_in_progress = True
        try:
            ident = self.client.submit("system.stop")
            events = self._wait(ident)
        except BaseException:
            with self._motion_lock:
                self._stop_failed = True
            raise
        finally:
            with self._motion_lock:
                self._stop_in_progress = False
        # A previous failed stop cannot be repaired by an unqualified retry.
        return events
