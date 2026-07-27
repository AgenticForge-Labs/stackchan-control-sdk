import json

import pytest

from stackchan_control.external_protocol import (
    PREFIX,
    ExternalProtocolError,
    decode_event_line,
    encode_command,
)


def test_encode_command() -> None:
    command_id, line = encode_command("system.ping", command_id="abc")
    assert command_id == "abc"
    assert line.startswith(PREFIX.encode())
    assert json.loads(line.decode()[len(PREFIX) :]) == {
        "id": "abc",
        "method": "system.ping",
        "params": {},
    }


def test_decode_ignores_console_logs() -> None:
    assert decode_event_line("I (123) normal ESP-IDF log") is None


def test_decode_event() -> None:
    event = decode_event_line('@AF {"id":"abc","event":"completed","result":{"x":1}}')
    assert event is not None
    assert event.command_id == "abc"
    assert event.result == {"x": 1}


def test_decode_rejects_bad_event() -> None:
    with pytest.raises(ExternalProtocolError):
        decode_event_line("@AF []")
