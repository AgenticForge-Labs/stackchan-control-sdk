"""Exercise native controls against an in-memory transport."""

import asyncio

from stackchan_control import (
    AvatarUpdate,
    FeatureUpdate,
    Keyframe,
    ServoUpdate,
    StackChan,
)
from stackchan_control.transports import MemoryTransport


def neutral_feature() -> FeatureUpdate:
    return FeatureUpdate(x=0, y=0, rotation=0, weight=0, size=0)


async def main() -> None:
    transport = MemoryTransport()
    async with StackChan(transport) as robot:
        # set_pose accepts ordinary degrees and converts to native tenths.
        await robot.set_pose(yaw=20, pitch=45, speed=25)
        await robot.update_avatar(AvatarUpdate(mouth=FeatureUpdate(size=8)))
        await robot.play_sequence(
            [
                Keyframe(
                    duration_ms=300,
                    left_eye=neutral_feature(),
                    right_eye=neutral_feature(),
                    mouth=neutral_feature(),
                    yaw=ServoUpdate(angle=200, speed=100),
                    pitch=ServoUpdate(angle=450, speed=100),
                    left_rgb_color="#ff8800",
                    right_rgb_color="#ff8800",
                )
            ]
        )

    print(f"Generated {len(transport.frames)} native StackChan frames")


if __name__ == "__main__":
    asyncio.run(main())
