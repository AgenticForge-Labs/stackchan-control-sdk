import pytest

from stackchan_control.models import (
    AvatarUpdate,
    FeatureUpdate,
    Keyframe,
    MotionUpdate,
    ServoUpdate,
)


def test_native_json_field_names() -> None:
    avatar = AvatarUpdate(
        left_eye=FeatureUpdate(x=12, y=-4, rotation=5),
        mouth=FeatureUpdate(size=8),
    )
    motion = MotionUpdate(yaw=ServoUpdate(angle=200, speed=30))

    assert avatar.to_dict() == {
        "leftEye": {"x": 12, "y": -4, "rotation": 5},
        "mouth": {"size": 8},
    }
    assert motion.to_dict() == {"yawServo": {"angle": 200, "speed": 30}}


def test_motion_modes_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        ServoUpdate(angle=10, rotate=2)
    with pytest.raises(ValueError, match="different firmware motion modes"):
        ServoUpdate(angle=10, speed=20, stiffness=100.0)


def test_native_ranges_are_validated() -> None:
    with pytest.raises(ValueError, match="x and y"):
        FeatureUpdate(x=5)
    with pytest.raises(ValueError, match="rotation"):
        FeatureUpdate(rotation=3601)
    with pytest.raises(ValueError, match="speed"):
        ServoUpdate(angle=100, speed=1001)


def test_keyframe_serialization() -> None:
    frame = Keyframe(
        duration_ms=500,
        yaw=ServoUpdate(angle=150, speed=20),
        left_rgb_color="#ff0000",
    )
    assert frame.to_dict() == {
        "durationMs": 500,
        "yawServo": {"angle": 150, "speed": 20},
        "leftRgbColor": "#ff0000",
    }
