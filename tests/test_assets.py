import json
from dataclasses import replace
from pathlib import Path

import pytest

from stackchan_control.assets import list_assets, load_asset, validate_asset
from stackchan_control.cli import main
from stackchan_control.models import AvatarUpdate, FeatureUpdate


def document(**changes):
    data = {
        "schema_version": 1,
        "id": "demo",
        "kind": "pose",
        "steps": [{"at_s": 0, "operation": "face", "parameters": {"mouth": {"size": 3}}}],
    }
    data.update(changes)
    return data


def write(path, value):
    path.write_text(json.dumps(value))
    return path


def test_pack_is_sorted_and_hash_detects_mutation(tmp_path):
    a = write(tmp_path / "z.json", document(id="a"))
    write(tmp_path / "a.json", document(id="z"))
    assets = list_assets(tmp_path)
    assert [asset.id for asset in assets] == ["a", "z"]
    first = assets[0].revision
    write(a, document(id="a", description="changed"))
    assert load_asset(a).revision != first


def test_descriptor_and_content_are_bound_to_revision(tmp_path):
    asset = load_asset(write(tmp_path / "a.json", document()))
    descriptor = asset.descriptor()
    assert descriptor["id"] == "stackchan/demo"
    assert descriptor["resources"] == ["face.mouth"]
    assert descriptor["revision"] == asset.revision
    assert descriptor["duration_s"] is None
    assert descriptor["device_compatibility"]["status"] == "unchecked"
    altered = replace(
        asset, steps=(replace(asset.steps[0], update=AvatarUpdate(mouth=FeatureUpdate(size=4))),)
    )
    with pytest.raises(ValueError, match="does not match"):
        validate_asset(altered)


def test_invalid_and_duplicate_assets_fail_closed(tmp_path):
    write(tmp_path / "a.json", document())
    write(tmp_path / "b.json", document())
    with pytest.raises(ValueError, match="duplicate"):
        list_assets(tmp_path)
    for params in ({"yaw": {"angle": 1290, "speed": 1}}, {"yaw": {"angle": True, "speed": 1}}):
        bad = document(steps=[{"at_s": 0, "operation": "head", "parameters": params}])
        with pytest.raises(ValueError):
            load_asset(write(tmp_path / "bad.json", bad))
    with pytest.raises(ValueError, match="unsupported operation"):
        load_asset(
            write(
                tmp_path / "bad.json",
                document(steps=[{"at_s": 0, "operation": "animation.play", "parameters": {}}]),
            )
        )


def test_asset_cli_never_opens_serial(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("catalog inspection opened a device")

    monkeypatch.setattr("stackchan_control.cli.RoutedSerialClient.open", forbidden)
    pack = Path(__file__).resolve().parents[1] / "examples/assets"
    assert main(["assets", "--pack", str(pack)]) == 0
    assert [asset["id"] for asset in json.loads(capsys.readouterr().out)["result"]] == [
        "stackchan/face-neutral",
        "stackchan/head-and-face",
    ]


def test_play_rejects_stale_revision_before_connecting(monkeypatch, capsys, tmp_path):
    write(tmp_path / "a.json", document())

    def forbidden(*args, **kwargs):
        raise AssertionError("stale asset opened a device")

    monkeypatch.setattr("stackchan_control.cli.RoutedSerialClient.open", forbidden)
    assert (
        main(
            [
                "--port",
                "fake",
                "play",
                "--pack",
                str(tmp_path),
                "--id",
                "stackchan/demo",
                "--revision",
                "stale",
            ]
        )
        == 1
    )
    assert "revision" in json.loads(capsys.readouterr().err)["error"]["message"]
