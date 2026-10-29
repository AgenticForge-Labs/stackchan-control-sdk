import json

import pytest
from jsonschema import Draft202012Validator
from test_cli import Client

from stackchan_control.capabilities import SCHEMA_VERSION, capability_schema
from stackchan_control.cli import main
from stackchan_control.external_control import CAPABILITIES


@pytest.mark.parametrize(
    ("ident", "valid", "invalid"),
    [
        ("avatar.update", {"mouth": {"size": 3}}, {"mouth": {"x": 3}}),
        ("avatar.update", {"leftEye": {"x": 3, "y": 4}}, {"yawServo": {"angle": 0}}),
        (
            "motion.update.position_only",
            {"yawServo": {"angle": -1280, "speed": 50}},
            {"yawServo": {"angle": 1281, "speed": 50}},
        ),
        (
            "motion.update.position_only",
            {"pitchServo": {"angle": 30, "speed": 0}},
            {"pitchServo": {"angle": 30, "speed": 2, "rotate": 1}},
        ),
        ("lights.update", {"leftRgbColor": "#abcdef"}, {"leftRgbColor": "red"}),
        (
            "external_lights.update",
            {"pixels": ["#123456"] * 37, "brightness": 8},
            {"pixels": ["#123456"] * 36, "brightness": 8},
        ),
        ("system.stop", {}, {"unexpected": 1}),
    ],
)
def test_schema_validates_native_payloads(ident, valid, invalid):
    schema = capability_schema(ident)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    assert validator.is_valid(valid)
    assert not validator.is_valid(invalid)


def test_registry_copies_and_omits_gated_animation():
    assert "animation.play" not in CAPABILITIES
    schema = capability_schema("avatar.update")
    schema["properties"].clear()
    assert "mouth" in capability_schema("avatar.update")["properties"]
    for capability in CAPABILITIES.values():
        assert capability.to_dict()["schema_version"] == SCHEMA_VERSION
        Draft202012Validator.check_schema(capability.to_dict()["parameters_schema"])


def test_cli_discovery_uses_same_registry_and_firmware_intersection(monkeypatch, capsys):
    client = Client()
    monkeypatch.setattr("stackchan_control.cli.RoutedSerialClient.open", lambda port: client)
    assert main(["--port", "fake", "discover"]) == 0
    controls = json.loads(capsys.readouterr().out)["result"]["controls"]
    assert {control["id"] for control in controls} == {"avatar.update", "system.state"}
    avatar = next(control for control in controls if control["id"] == "avatar.update")
    assert avatar == CAPABILITIES["avatar.update"].to_dict()
