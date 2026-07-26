"""Host-side controls for M5Stack StackChan."""

from .client import StackChan
from .models import AvatarUpdate, FeatureUpdate, Keyframe, MotionUpdate, ServoUpdate
from .protocol import DataType, Packet, decode_packet, encode_packet

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
    "encode_packet",
]

__version__ = "0.1.0"
