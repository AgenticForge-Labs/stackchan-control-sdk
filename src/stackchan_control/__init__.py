"""Host-side controls for M5Stack StackChan."""

from .assets import AssetStep, NativeAsset, list_assets, load_asset
from .capabilities import SCHEMA_VERSION, capability_schema
from .client import StackChan
from .external_control import BuiltinLights, ExternalControl, FirmwareRejected, NativeCapability
from .lighting import LightingCleanupError, LightingInterrupted, LightingResult, sustain_neohex
from .models import AvatarUpdate, FeatureUpdate, Keyframe, MotionUpdate, ServoUpdate
from .neohex import NeoHexFrame
from .playback import PlaybackInterrupted, StepResult, play_asset
from .protocol import DataType, Packet, decode_packet, encode_packet
from .routed_serial import RoutedSerialClient, RoutedSerialError, UnknownOutcome
from .units import degrees_to_native_angle, native_angle_to_degrees

__all__ = [
    "AvatarUpdate",
    "AssetStep",
    "BuiltinLights",
    "DataType",
    "FeatureUpdate",
    "ExternalControl",
    "FirmwareRejected",
    "Keyframe",
    "LightingCleanupError",
    "LightingInterrupted",
    "LightingResult",
    "MotionUpdate",
    "NeoHexFrame",
    "NativeCapability",
    "NativeAsset",
    "Packet",
    "PlaybackInterrupted",
    "ServoUpdate",
    "RoutedSerialClient",
    "RoutedSerialError",
    "SCHEMA_VERSION",
    "StackChan",
    "StepResult",
    "UnknownOutcome",
    "capability_schema",
    "decode_packet",
    "degrees_to_native_angle",
    "encode_packet",
    "list_assets",
    "load_asset",
    "native_angle_to_degrees",
    "play_asset",
    "sustain_neohex",
]

__version__ = "0.3.0"
