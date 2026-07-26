"""High-level access to StackChan-native device capabilities."""

from __future__ import annotations

from types import TracebackType

from .models import AvatarUpdate, Keyframe, MotionUpdate, ServoUpdate
from .protocol import DataType, encode_json_packet, encode_packet
from .transports.base import Transport


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
        if self._enforce_pitch_limits and update.pitch is not None:
            pitch = update.pitch.angle
            if pitch is not None and not 5 <= pitch <= 85:
                raise ValueError("pitch angle must be between 5 and 85 degrees")
        await self._transport.send(
            encode_json_packet(DataType.CONTROL_MOTION, update.to_dict())
        )

    async def set_pose(
        self,
        *,
        yaw: int | None = None,
        pitch: int | None = None,
        speed: int | None = None,
    ) -> None:
        if yaw is None and pitch is None:
            raise ValueError("at least one of yaw or pitch is required")
        await self.update_motion(
            MotionUpdate(
                yaw=ServoUpdate(angle=yaw, speed=speed) if yaw is not None else None,
                pitch=ServoUpdate(angle=pitch, speed=speed) if pitch is not None else None,
            )
        )

    async def play_sequence(self, keyframes: list[Keyframe]) -> None:
        if not keyframes:
            raise ValueError("keyframes must not be empty")
        await self._transport.send(
            encode_json_packet(DataType.DANCE_SEQUENCE, [frame.to_dict() for frame in keyframes])
        )

    async def heartbeat(self) -> None:
        await self._transport.send(encode_packet(DataType.HEARTBEAT_PING))
