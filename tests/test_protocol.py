import pytest

from stackchan_control.protocol import (
    DataType,
    ProtocolError,
    decode_packet,
    encode_json_packet,
    encode_packet,
)


def test_binary_packet_round_trip() -> None:
    frame = encode_packet(DataType.CONTROL_MOTION, b"{}")
    assert frame == b"\x04\x00\x00\x00\x02{}"
    packet = decode_packet(frame)
    assert packet.data_type is DataType.CONTROL_MOTION
    assert packet.payload == b"{}"


def test_json_packet_is_compact() -> None:
    packet = decode_packet(encode_json_packet(DataType.CONTROL_AVATAR, {"mouth": {"size": 2}}))
    assert packet.json() == {"mouth": {"size": 2}}
    assert packet.payload == b'{"mouth":{"size":2}}'


def test_rejects_bad_declared_length() -> None:
    with pytest.raises(ProtocolError, match="declared payload length"):
        decode_packet(b"\x03\x00\x00\x00\x02{")
