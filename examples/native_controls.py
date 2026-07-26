"""Exercise native controls against an in-memory transport."""

import asyncio

from stackchan_control import AvatarUpdate, FeatureUpdate, Keyframe, StackChan
from stackchan_control.transports import MemoryTransport


async def main() -> None:
    transport = MemoryTransport()
    async with StackChan(transport) as robot:
        await robot.set_pose(yaw=20, pitch=45, speed=25)
        await robot.update_avatar(AvatarUpdate(mouth=FeatureUpdate(size=8)))
        await robot.play_sequence(
            [
                Keyframe(duration_ms=300, left_rgb_color="#ff8800"),
                Keyframe(duration_ms=300, right_rgb_color="#ff8800"),
            ]
        )

    print(f"Generated {len(transport.frames)} native StackChan frames")


if __name__ == "__main__":
    asyncio.run(main())
