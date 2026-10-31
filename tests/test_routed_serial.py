import json
import queue

import pytest

from stackchan_control.routed_serial import RoutedSerialClient, RoutedSerialError, UnknownOutcome


class Wire:
    def __init__(self):
        self.lines = queue.Queue()
        self.commands = []
        self.closed = False

    def write(self, data):
        self.commands.append(json.loads(data.decode()[4:]))
        return len(data)

    def flush(self):
        pass

    def readline(self):
        try:
            return self.lines.get(timeout=0.01)
        except queue.Empty:
            return b""

    def close(self):
        self.closed = True

    def event(self, ident, event):
        self.lines.put(("@AF " + json.dumps({"id": ident, "event": event}) + "\n").encode())


def test_interleaved_stop_and_motion_are_routed():
    wire = Wire()
    client = RoutedSerialClient(wire)
    try:
        motion = client.submit("motion.update", {})
        stop = client.submit("system.stop")
        wire.event(motion, "accepted")
        wire.event(stop, "accepted")
        wire.event(motion, "cancelled")
        wire.event(stop, "completed")
        assert [e.event for e in client.wait(stop)] == ["accepted", "completed"]
        assert [e.event for e in client.wait(motion)] == ["accepted", "cancelled"]
    finally:
        client.close()


def test_timeout_is_unknown_and_late_result_remains_available():
    wire = Wire()
    client = RoutedSerialClient(wire)
    try:
        ident = client.submit("motion.update")
        with pytest.raises(UnknownOutcome, match="timeout"):
            client.wait(ident, timeout=0)
        wire.event(ident, "completed")
        assert client.wait(ident)[-1].event == "completed"
        assert len(wire.commands) == 1
    finally:
        client.close()


def test_malformed_input_fails_connection_without_reconnect():
    wire = Wire()
    client = RoutedSerialClient(wire)
    try:
        ident = client.submit("system.state")
        wire.lines.put(b"@AF invalid\n")
        with pytest.raises(UnknownOutcome, match="connection lost"):
            client.wait(ident)
        with pytest.raises(RoutedSerialError, match="unavailable"):
            client.submit("system.state")
        assert len(wire.commands) == 1
    finally:
        client.close()


def test_firmware_rejection_is_returned_as_terminal_event():
    wire = Wire()
    client = RoutedSerialClient(wire)
    try:
        ident = client.submit("motion.update")
        wire.event(ident, "failed")
        assert client.wait(ident)[-1].event == "failed"
    finally:
        client.close()


def test_close_leaves_pending_command_unknown_and_prevents_new_commands():
    client = RoutedSerialClient(Wire())
    ident = client.submit("motion.update")
    client.close()
    with pytest.raises(UnknownOutcome, match="connection lost"):
        client.wait(ident)
    with pytest.raises(RoutedSerialError, match="closed"):
        client.submit("system.stop")


def test_open_sets_finite_write_timeout_and_does_not_wait_for_flush(monkeypatch):
    wire = Wire()
    wire.flush = lambda: (_ for _ in ()).throw(AssertionError("flush must not be called"))
    settings = {}

    def open_wire(port, baudrate, **kwargs):
        settings.update(kwargs)
        return wire

    monkeypatch.setattr("serial.Serial", open_wire)
    client = RoutedSerialClient.open("fake")
    try:
        ident = client.submit("system.stop")
        wire.event(ident, "completed")
        assert client.wait(ident)[-1].event == "completed"
        assert settings == {"timeout": 0.1, "write_timeout": 0.25}
    finally:
        client.close()


def test_partial_serial_write_never_triggers_automatic_retry_or_reconnect():
    wire = Wire()
    transmitted = []

    def partial_write(data):
        transmitted.append(data)
        return len(data) - 1

    wire.write = partial_write
    client = RoutedSerialClient(wire)
    try:
        with pytest.raises(UnknownOutcome, match="outcome unknown"):
            client.submit("motion.update", {"yawServo": {"angle": 50, "speed": 20}})
        with pytest.raises(RoutedSerialError, match="unavailable"):
            client.submit("motion.update", {"yawServo": {"angle": 50, "speed": 20}})
        assert len(transmitted) == 1
    finally:
        client.close()
