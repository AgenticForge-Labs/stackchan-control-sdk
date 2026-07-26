"""Typed representations of StackChan's native JSON controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class FeatureDict(TypedDict, total=False):
    x: int
    y: int
    rotation: int
    weight: int
    size: int


class SpringDict(TypedDict, total=False):
    stiffness: float
    damping: float


class ServoDict(TypedDict, total=False):
    angle: int
    speed: int
    rotate: int
    spring: SpringDict


@dataclass(frozen=True, slots=True)
class FeatureUpdate:
    x: int | None = None
    y: int | None = None
    rotation: int | None = None
    weight: int | None = None
    size: int | None = None

    def to_dict(self) -> FeatureDict:
        result: FeatureDict = {}
        values = {
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "weight": self.weight,
            "size": self.size,
        }
        for key, value in values.items():
            if value is not None:
                result[key] = value  # type: ignore[literal-required]
        return result


@dataclass(frozen=True, slots=True)
class ServoUpdate:
    angle: int | None = None
    speed: int | None = None
    rotate: int | None = None
    stiffness: float | None = None
    damping: float | None = None

    def __post_init__(self) -> None:
        if self.rotate is not None and self.angle is not None:
            raise ValueError("rotate and angle are mutually exclusive")
        if self.speed is not None and self.angle is None:
            raise ValueError("speed requires angle")
        if (self.stiffness is not None or self.damping is not None) and self.angle is None:
            raise ValueError("spring parameters require angle")
        if self.speed is not None and (self.stiffness is not None or self.damping is not None):
            raise ValueError("speed and spring parameters select different firmware motion modes")

    def to_dict(self) -> ServoDict:
        result: ServoDict = {}
        if self.rotate is not None:
            result["rotate"] = self.rotate
            return result
        if self.angle is not None:
            result["angle"] = self.angle
        if self.speed is not None:
            result["speed"] = self.speed
        spring: SpringDict = {}
        if self.stiffness is not None:
            spring["stiffness"] = self.stiffness
        if self.damping is not None:
            spring["damping"] = self.damping
        if spring:
            result["spring"] = spring
        return result


@dataclass(frozen=True, slots=True)
class AvatarUpdate:
    left_eye: FeatureUpdate | None = None
    right_eye: FeatureUpdate | None = None
    mouth: FeatureUpdate | None = None

    def to_dict(self) -> dict[str, FeatureDict]:
        result: dict[str, FeatureDict] = {}
        if self.left_eye is not None:
            result["leftEye"] = self.left_eye.to_dict()
        if self.right_eye is not None:
            result["rightEye"] = self.right_eye.to_dict()
        if self.mouth is not None:
            result["mouth"] = self.mouth.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class MotionUpdate:
    yaw: ServoUpdate | None = None
    pitch: ServoUpdate | None = None

    def to_dict(self) -> dict[str, ServoDict]:
        result: dict[str, ServoDict] = {}
        if self.yaw is not None:
            result["yawServo"] = self.yaw.to_dict()
        if self.pitch is not None:
            result["pitchServo"] = self.pitch.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class Keyframe:
    duration_ms: int
    left_eye: FeatureUpdate | None = None
    right_eye: FeatureUpdate | None = None
    mouth: FeatureUpdate | None = None
    yaw: ServoUpdate | None = None
    pitch: ServoUpdate | None = None
    left_rgb_color: str | None = None
    right_rgb_color: str | None = None

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"durationMs": self.duration_ms}
        if self.left_eye is not None:
            result["leftEye"] = self.left_eye.to_dict()
        if self.right_eye is not None:
            result["rightEye"] = self.right_eye.to_dict()
        if self.mouth is not None:
            result["mouth"] = self.mouth.to_dict()
        if self.yaw is not None:
            result["yawServo"] = self.yaw.to_dict()
        if self.pitch is not None:
            result["pitchServo"] = self.pitch.to_dict()
        if self.left_rgb_color is not None:
            result["leftRgbColor"] = self.left_rgb_color
        if self.right_rgb_color is not None:
            result["rightRgbColor"] = self.right_rgb_color
        return result
