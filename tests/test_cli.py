import json

import pytest

from stackchan_control.cli import main
from stackchan_control.external_protocol import ExternalEvent


class Client:
    def __init__(self):
        self.closed = False
        self.requests = []

    def submit(self, method, params=None):
        self.requests.append((method, params))
        return str(len(self.requests))

    def wait(self, ident, *, timeout):
        method = self.requests[int(ident) - 1][0]
        if method == "system.capabilities":
            result = {"protocol_version": "1.0", "capabilities": ["avatar.update", "system.state"]}
        else:
            result = {}
        return (ExternalEvent("completed", ident, result=result),)

    def close(self):
        self.closed = True


def test_cli_face_uses_typed_external_control(monkeypatch, capsys):
    client = Client()
    monkeypatch.setattr("stackchan_control.cli.RoutedSerialClient.open", lambda port: client)
    assert main(["--port", "fake", "face", "--feature", "mouth", "--size", "10"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    assert client.requests[-1] == ("avatar.update", {"mouth": {"size": 10}})
    assert client.closed


def test_cli_face_scale_rejects_unapproved_ratio_before_usb(monkeypatch, capsys):
    monkeypatch.setattr(
        "stackchan_control.cli.RoutedSerialClient.open",
        lambda port: (_ for _ in ()).throw(AssertionError("must not open USB")),
    )
    with pytest.raises(SystemExit):
        main(["--port", "fake", "face-scale", "--percent", "169"])


def test_cli_assets_reports_schedule_span_without_opening_usb(tmp_path, monkeypatch, capsys):
    pack = tmp_path / "assets"
    pack.mkdir()
    (pack / "sequence.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "demo-sequence",
                "kind": "sequence",
                "steps": [
                    {"at_s": 0, "operation": "face", "parameters": {"mouth": {"size": 3}}},
                    {
                        "at_s": 2.5,
                        "operation": "face",
                        "parameters": {"mouth": {"size": 4}},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "stackchan_control.cli.RoutedSerialClient.open",
        lambda port: (_ for _ in ()).throw(AssertionError("asset listing opened USB")),
    )

    assert main(["assets", "--pack", str(pack)]) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert result[0]["id"] == "stackchan/demo-sequence"
    assert result[0]["duration_s"] == 2.5


def test_cli_rejects_invalid_face_without_motion(monkeypatch, capsys):
    client = Client()
    monkeypatch.setattr("stackchan_control.cli.RoutedSerialClient.open", lambda port: client)
    assert main(["--port", "fake", "face", "--feature", "mouth", "--size", "101"]) == 1
    assert json.loads(capsys.readouterr().err)["error"]["type"] == "ValueError"
    assert client.requests == []
    assert client.closed


def test_cli_live_commands_use_facade_and_structured_results(monkeypatch, capsys):
    from test_external_control import Firmware

    from stackchan_control.routed_serial import RoutedSerialClient

    class CompleteFirmware(Firmware):
        def write(self, data):
            count = super().write(data)
            command = self.commands[-1]
            if command["method"] == "motion.update":
                self.emit(command["id"], "completed")
            return count

    for arguments, expected in (
        (["discover"], "system.capabilities"),
        (["state"], "system.state"),
        (["face-scale", "--percent", "170"], "display.face_scale"),
        (["head", "--yaw", "10", "--speed", "20"], "motion.update"),
        (["lights", "--left-color", "#ff0000"], "lights.update"),
        (["neohex", "--color", "#ff0000"], "external_lights.update"),
        (["stop"], "system.stop"),
    ):
        firmware = CompleteFirmware()
        monkeypatch.setattr(
            "stackchan_control.cli.RoutedSerialClient.open",
            lambda port, wire=firmware: RoutedSerialClient(wire),
        )
        assert main(["--port", "fake", "--timeout", "0.5", *arguments]) == 0
        assert json.loads(capsys.readouterr().out)["ok"] is True
        assert firmware.commands[-1]["method"] == expected


def test_cli_reports_firmware_rejection_and_unknown_outcome(monkeypatch, capsys):
    from test_external_control import Firmware

    from stackchan_control.routed_serial import RoutedSerialClient

    rejected = Firmware()
    rejected.reject = "lights.update"
    monkeypatch.setattr(
        "stackchan_control.cli.RoutedSerialClient.open", lambda port: RoutedSerialClient(rejected)
    )
    assert main(["--port", "fake", "lights", "--left-color", "#ff0000"]) == 1
    assert json.loads(capsys.readouterr().err)["error"]["type"] == "FirmwareRejected"

    pending = Firmware()
    monkeypatch.setattr(
        "stackchan_control.cli.RoutedSerialClient.open", lambda port: RoutedSerialClient(pending)
    )
    assert (
        main(["--port", "fake", "--timeout", "0.02", "head", "--yaw", "10", "--speed", "20"]) == 1
    )
    assert json.loads(capsys.readouterr().err)["error"]["type"] == "UnknownOutcome"
    assert sum(command["method"] == "motion.update" for command in pending.commands) == 1
