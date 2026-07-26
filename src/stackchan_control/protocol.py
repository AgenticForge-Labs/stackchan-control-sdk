"""Packet framing used by the stock StackChan Avatar WebSocket service.

The stock firmware uses a one-byte type followed by a four-byte payload length
and the raw payload. JSON is UTF-8 encoded for avatar, motion, and dance data.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

_HEADER = struct.Struct(">BI")


class ProtocolError(ValueError):
    """Raised when a StackChan packet is malformed."""


class DataType(IntEnum):
    """Message types mirrored from M5Stack's stock Avatar firmware."""

    OPUS = 0x01
    JPEG = 0x02
    CONTROL_AVATAR = 0x03
    CONTROL_MOTION = 0x04
    START_CAMERA_STREAM = 0x05
    STOP_CAMERA_STREAM = 0x06
    TEXT_MESSAGE = 0x07
    REQUEST_CALL = 0x09
    DECLINE_CALL = 0x0A
    ACCEPT_CALL = 0x0B
    END_CALL = 0x0C
    SET_DEVICE_NAME = 0x0D
    GET_DEVICE_NAME = 0x0E
    HEARTBEAT_PING = 0x10
    HEARTBEAT_PONG = 0x11
    VIDEO_MODE_ON = 0x12
    VIDEO_MODE_OFF = 0x13
    DANCE_SEQUENCE = 0x14
    START_AUDIO_STREAM = 0x18
    STOP_AUDIO_STREAM = 0x19


@dataclass(frozen=True, slots=True)
class Packet:
    """A decoded stock Avatar WebSocket packet."""

    data_type: DataType
    payload: bytes

    def json(self) -> Any:
        """Decode a JSON payload."""
        return json.loads(self.payload.decode("utf-8"))


def encode_packet(data_type: DataType, payload: bytes = b"") -> bytes:
    """Encode one stock WebSocket binary frame."""
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    return _HEADER.pack(int(data_type), len(payload)) + payload


def encode_json_packet(data_type: DataType, value: Any) -> bytes:
    """Encode compact deterministic JSON in a stock WebSocket binary frame."""
    payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return encode_packet(data_type, payload)


def decode_packet(frame: bytes) -> Packet:
    """Decode and validate one stock WebSocket binary frame."""
    if len(frame) < _HEADER.size:
        raise ProtocolError("frame is shorter than the five-byte header")
    raw_type, declared_length = _HEADER.unpack_from(frame)
    payload = frame[_HEADER.size :]
    if declared_length != len(payload):
        raise ProtocolError(
            f"declared payload length {declared_length} does not match {len(payload)} bytes"
        )
    try:
        data_type = DataType(raw_type)
    except ValueError as exc:
        raise ProtocolError(f"unknown data type 0x{raw_type:02x}") from exc
    return Packet(data_type=data_type, payload=payload)
