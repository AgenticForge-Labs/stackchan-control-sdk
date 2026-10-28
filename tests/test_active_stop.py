import json

import pytest

from stackchan_control.serial_client import SerialControlClient
from tools.verify_active_stop import interrupt_motion


class Wire:
    def __init__(self, *, complete_early=False, omit_stop=False):
        self.queue = []
        self.motion_id = None
        self.complete_early = complete_early
        self.omit_stop = omit_stop
        self.methods = []

    def write(self, data):
        packet = json.loads(data.decode()[4:])
        ident = packet["id"]
        self.methods.append(packet["method"])
        if packet["method"] == "motion.update":
            self.motion_id = ident
            self.queue.append({"id": ident, "event": "accepted"})
            if self.complete_early:
                self.queue.append({"id": ident, "event": "completed"})
        elif not self.omit_stop:
            self.queue.extend(
                [
                    {"id": ident, "event": "accepted"},
                    {"id": self.motion_id, "event": "cancelled"},
                    {"id": ident, "event": "completed"},
                ]
            )

    def flush(self):
        pass

    def readline(self):
        if not self.queue:
            return b""
        return ("@AF " + json.dumps(self.queue.pop(0)) + "\n").encode()


def setup_client(monkeypatch, **kwargs):
    ticks = iter(i * 0.05 for i in range(1000))
    monkeypatch.setattr("tools.verify_active_stop.time.monotonic", lambda: next(ticks))
    client = SerialControlClient("FAKE")
    wire = Wire(**kwargs)
    client._serial = wire
    return client, wire


def test_stop_retains_interleaved_motion_cancellation(monkeypatch):
    client, wire = setup_client(monkeypatch)
    evidence = {}
    interrupt_motion(client, evidence)
    assert wire.methods == ["motion.update", "system.stop"]
    assert evidence["command_status"] == "pass"
    assert [e["event"] for e in evidence["events"]] == [
        "accepted",
        "accepted",
        "cancelled",
        "completed",
    ]
    assert evidence["motion_id"] != evidence["stop_id"]


def test_completion_before_stop_is_not_cancellation(monkeypatch):
    client, _ = setup_client(monkeypatch, complete_early=True)
    evidence = {}
    with pytest.raises(RuntimeError, match="completed before cancellation"):
        interrupt_motion(client, evidence)
    assert "command_status" not in evidence


def test_missing_stop_response_times_out_with_evidence(monkeypatch):
    client, wire = setup_client(monkeypatch, omit_stop=True)
    evidence = {}
    with pytest.raises(TimeoutError):
        interrupt_motion(client, evidence)
    assert wire.methods == ["motion.update", "system.stop"]
    assert evidence["events"][0]["event"] == "accepted"
