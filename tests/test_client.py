import asyncio

import pytest

from stackchan_control import AvatarUpdate, FeatureUpdate, Keyframe, StackChan
from stackchan_control.protocol import DataType, decode_packet
from stackchan_control.transports import MemoryTransport


def test_client_emits_stock_native_messages() -> None:
    async def scenario() -> list[bytes]:
        transport = MemoryTransport()
        async with StackChan(transport) as robot:
            await robot.set_pose(yaw=20, pitch=45, speed=30)
            await robot.update_avatar(AvatarUpdate(mouth=FeatureUpdate(size=7)))
            await robot.play_sequence([Keyframe(duration_ms=250, left_rgb_color="#00ff00")])
        return transport.frames

    frames = asyncio.run(scenario())
    assert [decode_packet(frame).data_type for frame in frames] == [
        DataType.CONTROL_MOTION,
        DataType.CONTROL_AVATAR,
        DataType.DANCE_SEQUENCE,
    ]
    assert decode_packet(frames[0]).json() == {
        "yawServo": {"angle": 20, "speed": 30},
        "pitchServo": {"angle": 45, "speed": 30},
    }


def test_default_pitch_guard() -> None:
    async def scenario() -> None:
        transport = MemoryTransport()
        async with StackChan(transport) as robot:
            await robot.set_pose(pitch=90)

    with pytest.raises(ValueError, match="between 5 and 85"):
        asyncio.run(scenario())
