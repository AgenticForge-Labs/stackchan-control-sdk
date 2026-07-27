"""Host-side controls for M5Stack StackChan."""

from .client import StackChan
from .models import AvatarUpdate, FeatureUpdate, Keyframe, MotionUpdate, ServoUpdate
from .protocol import DataType, Packet, decode_packet, encode_packet
from .units import degrees_to_native_angle, native_angle_to_degrees

__all__ = [
    "AvatarUpdate",
    "DataType",
    "FeatureUpdate",
    "Keyframe",
    "MotionUpdate",
    "Packet",
    "ServoUpdate",
    "StackChan",
    "decode_packet",
    "degrees_to_native_angle",
    "encode_packet",
    "native_angle_to_degrees",
]

__version__ = "0.2.0"
