import json

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


def test_cli_rejects_invalid_face_without_motion(monkeypatch, capsys):
    client = Client()
    monkeypatch.setattr("stackchan_control.cli.RoutedSerialClient.open", lambda port: client)
    assert main(["--port", "fake", "face", "--feature", "mouth", "--size", "101"]) == 1
    assert json.loads(capsys.readouterr().err)["error"]["type"] == "ValueError"
    assert client.requests == []
    assert client.closed
