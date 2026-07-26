"""High-level access to StackChan-native device capabilities."""

from __future__ import annotations

from types import TracebackType

from .models import AvatarUpdate, Keyframe, MotionUpdate, ServoUpdate
from .protocol import DataType, encode_json_packet, encode_packet
from .transports.base import Transport
from .units import (
    PITCH_MAX_TENTHS,
    PITCH_MIN_TENTHS,
    YAW_MAX_TENTHS,
    YAW_MIN_TENTHS,
    degrees_to_native_angle,
)


class StackChan:
    """Control StackChan using its native avatar, motion, and dance messages.

    This class intentionally contains no AgenticForge emotions or character
    semantics. Those mappings belong in Robo Puppeteer.
    """

    def __init__(self, transport: Transport, *, enforce_pitch_limits: bool = True) -> None:
        self._transport = transport
        self._enforce_pitch_limits = enforce_pitch_limits

    async def __aenter__(self) -> StackChan:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def connect(self) -> None:
        await self._transport.connect()

    async def close(self) -> None:
        await self._transport.close()

    async def update_avatar(self, update: AvatarUpdate) -> None:
        await self._transport.send(
            encode_json_packet(DataType.CONTROL_AVATAR, update.to_dict())
        )

    async def update_motion(self, update: MotionUpdate) -> None:
        """Send a low-level native motion update using tenths-of-a-degree angles."""
        if (
            update.yaw is not None
            and update.yaw.angle is not None
            and not YAW_MIN_TENTHS <= update.yaw.angle <= YAW_MAX_TENTHS
        ):
            raise ValueError("native yaw angle must be between -1280 and 1280 tenths")
        if (
            self._enforce_pitch_limits
            and update.pitch is not None
            and update.pitch.angle is not None
            and not PITCH_MIN_TENTHS <= update.pitch.angle <= PITCH_MAX_TENTHS
        ):
            raise ValueError("native pitch angle must be between 30 and 870 tenths")
        await self._transport.send(
            encode_json_packet(DataType.CONTROL_MOTION, update.to_dict())
        )

    async def set_pose(
        self,
        *,
        yaw: float | None = None,
        pitch: float | None = None,
        speed: int | None = None,
    ) -> None:
        """Set a pose in ordinary degrees.

        The upstream wire protocol uses integer tenths of a degree. This method
        performs that conversion. The default high-level pitch guard uses the
        conservative 5–85 degree range even though the native firmware clamps at
        approximately 3–87 degrees.
        """
        if yaw is None and pitch is None:
            raise ValueError("at least one of yaw or pitch is required")
        if yaw is not None and not -128 <= yaw <= 128:
            raise ValueError("yaw must be between -128 and 128 degrees")
        if self._enforce_pitch_limits and pitch is not None and not 5 <= pitch <= 85:
            raise ValueError("pitch must be between 5 and 85 degrees")
        await self.update_motion(
            MotionUpdate(
                yaw=(
                    ServoUpdate(angle=degrees_to_native_angle(yaw), speed=speed)
                    if yaw is not None
                    else None
                ),
                pitch=(
                    ServoUpdate(angle=degrees_to_native_angle(pitch), speed=speed)
                    if pitch is not None
                    else None
                ),
            )
        )

    async def play_sequence(self, keyframes: list[Keyframe]) -> None:
        if not keyframes:
            raise ValueError("keyframes must not be empty")
        if not all(frame.is_complete() for frame in keyframes):
            raise ValueError(
                "every native keyframe must explicitly define both eyes, mouth, "
                "yaw, pitch, servo speeds, and both RGB colors"
            )
        await self._transport.send(
            encode_json_packet(DataType.DANCE_SEQUENCE, [frame.to_dict() for frame in keyframes])
        )

    async def heartbeat(self) -> None:
        await self._transport.send(encode_packet(DataType.HEARTBEAT_PING))
