"""Validated, explicitly configured native pose and sequence assets.

Asset documents describe host-driven updates, not firmware native animations.
Loading them never opens a device or performs an operation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from .external_control import BuiltinLights
from .models import AvatarUpdate, FeatureUpdate, MotionUpdate, ServoUpdate

_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
_MAX_BYTES = 1_000_000
_MAX_STEPS = 1000
_MAX_DURATION = 300.0


@dataclass(frozen=True)
class AssetStep:
    at_s: float
    operation: Literal["head", "face", "lights"]
    update: MotionUpdate | AvatarUpdate | BuiltinLights


@dataclass(frozen=True)
class NativeAsset:
    id: str
    kind: Literal["pose", "sequence"]
    revision: str
    description: str
    steps: tuple[AssetStep, ...]
    _source_bytes: bytes = field(default=b"", repr=False)

    def descriptor(self) -> dict[str, Any]:
        resources: set[str] = set()
        for step in self.steps:
            if step.operation == "head":
                resources.add("head.pose")
            elif step.operation == "face" and isinstance(step.update, AvatarUpdate):
                if step.update.left_eye is not None or step.update.right_eye is not None:
                    resources.add("face.eyes")
                if step.update.mouth is not None:
                    resources.add("face.mouth")
            elif step.operation == "lights":
                resources.add("lights.builtin")
        return {
            "id": f"stackchan/{self.id}",
            "kind": self.kind,
            "source": "operator-configured-local-pack",
            "revision": self.revision,
            "description": self.description,
            "duration_s": None,
            "resources": sorted(resources),
            "parameters_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "calibration_reference": None,
            "device_compatibility": {"protocol": "external-control-v1", "status": "unchecked"},
            "audio_association": None,
        }


def _object(value: Any, allowed: set[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError(f"{name} must be an object with only {sorted(allowed)}")
    return value


def _servo(value: Any, name: str) -> ServoUpdate:
    data = _object(value, {"angle", "speed"}, name)
    if set(data) != {"angle", "speed"} or any(type(v) is not int for v in data.values()):
        raise ValueError(f"{name} requires integer angle and speed")
    low, high = (-1280, 1280) if name == "yaw" else (30, 870)
    if not low <= data["angle"] <= high or not 0 <= data["speed"] <= 1000:
        raise ValueError(f"{name} exceeds protocol limits")
    return ServoUpdate(angle=data["angle"], speed=data["speed"])


def _feature(value: Any, name: str) -> FeatureUpdate:
    data = _object(value, {"x", "y", "rotation", "weight", "size"}, name)
    if not data or any(type(v) is not int for v in data.values()):
        raise ValueError(f"{name} requires nonempty integer fields")
    return FeatureUpdate(**data)


def _step(value: Any) -> AssetStep:
    data = _object(value, {"at_s", "operation", "parameters"}, "step")
    if set(data) != {"at_s", "operation", "parameters"}:
        raise ValueError("step requires at_s, operation and parameters")
    at = data["at_s"]
    if isinstance(at, bool) or not isinstance(at, (float, int)) or not math.isfinite(at):
        raise ValueError("at_s must be finite")
    if not 0 <= at <= _MAX_DURATION:
        raise ValueError("at_s exceeds sequence limits")
    operation = data["operation"]
    if operation == "head":
        params = _object(data["parameters"], {"yaw", "pitch"}, "head parameters")
        if not params:
            raise ValueError("head parameters must not be empty")
        update: MotionUpdate | AvatarUpdate | BuiltinLights = MotionUpdate(
            yaw=_servo(params["yaw"], "yaw") if "yaw" in params else None,
            pitch=_servo(params["pitch"], "pitch") if "pitch" in params else None,
        )
    elif operation == "face":
        params = _object(data["parameters"], {"left_eye", "right_eye", "mouth"}, "face parameters")
        if not params:
            raise ValueError("face parameters must not be empty")
        update = AvatarUpdate(**{key: _feature(item, key) for key, item in params.items()})
    elif operation == "lights":
        params = _object(
            data["parameters"],
            {"left_color", "right_color", "left_duration", "right_duration"},
            "lights parameters",
        )
        update = BuiltinLights(**params)
        update.to_dict()
    else:
        raise ValueError(f"unsupported operation: {operation!r}")
    return AssetStep(at_s=float(at), operation=operation, update=update)


def load_asset(path: str | Path) -> NativeAsset:
    """Load one operator-chosen file, rejecting malformed or unbounded assets."""
    file = Path(path)
    if file.is_symlink() or not file.is_file():
        raise ValueError("asset must be a regular non-symlink file")
    with file.open("rb") as stream:
        raw = stream.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValueError("asset file exceeds size limit")
    return _parse_asset(raw)


def _parse_asset(raw: bytes) -> NativeAsset:
    data = _object(
        json.loads(raw), {"schema_version", "id", "kind", "description", "steps"}, "asset"
    )
    if data.get("schema_version") != 1 or type(data.get("schema_version")) is not int:
        raise ValueError("unsupported asset schema version")
    ident, kind = data.get("id"), data.get("kind")
    if not isinstance(ident, str) or not _ID.fullmatch(ident):
        raise ValueError("invalid asset ID")
    if kind not in ("pose", "sequence"):
        raise ValueError("asset kind must be pose or sequence")
    description = data.get("description", "")
    if not isinstance(description, str) or len(description) > 1024:
        raise ValueError("invalid asset description")
    values = data.get("steps")
    if not isinstance(values, list) or not 1 <= len(values) <= _MAX_STEPS:
        raise ValueError("asset must contain 1..1000 steps")
    steps = tuple(_step(item) for item in values)
    if any(a.at_s > b.at_s for a, b in zip(steps, steps[1:], strict=False)):
        raise ValueError("asset steps must be ordered")
    if kind == "pose" and (len(steps) != 1 or steps[0].at_s != 0):
        raise ValueError("pose must contain exactly one step at time zero")
    return NativeAsset(
        ident, kind, "sha256:" + hashlib.sha256(raw).hexdigest(), description, steps, raw
    )


def list_assets(directory: str | Path) -> tuple[NativeAsset, ...]:
    """Enumerate a configured pack; invalid files or duplicate IDs fail the pack."""
    root = Path(directory)
    if not root.is_dir():
        raise ValueError("asset pack directory does not exist")
    assets = tuple(load_asset(path) for path in sorted(root.glob("*.json")))
    if len({asset.id for asset in assets}) != len(assets):
        raise ValueError("duplicate asset ID")
    return tuple(sorted(assets, key=lambda asset: asset.id))


def validate_asset(asset: NativeAsset) -> None:
    """Revalidate the entire in-memory asset before any playback operation."""
    if not isinstance(asset, NativeAsset) or not _ID.fullmatch(asset.id):
        raise ValueError("invalid asset")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.revision):
        raise ValueError("invalid asset revision")
    if asset.kind not in ("pose", "sequence") or not 1 <= len(asset.steps) <= _MAX_STEPS:
        raise ValueError("invalid asset kind or step count")
    previous = -1.0
    for step in asset.steps:
        if not isinstance(step, AssetStep):
            raise ValueError("invalid asset step")
        expected = {"head": MotionUpdate, "face": AvatarUpdate, "lights": BuiltinLights}
        if step.operation not in expected or not isinstance(step.update, expected[step.operation]):
            raise ValueError("asset step operation and update do not match")
        params = {key: value for key, value in asdict(step.update).items() if value is not None}
        for key, value in tuple(params.items()):
            if isinstance(value, dict):
                params[key] = {k: v for k, v in value.items() if v is not None}
        checked = _step({"at_s": step.at_s, "operation": step.operation, "parameters": params})
        if checked.at_s < previous:
            raise ValueError("asset steps must be ordered")
        previous = checked.at_s
    if asset.kind == "pose" and (len(asset.steps) != 1 or asset.steps[0].at_s != 0):
        raise ValueError("pose must contain exactly one step at time zero")
    if len(asset._source_bytes) > _MAX_BYTES or not asset._source_bytes:
        raise ValueError("asset source snapshot is missing or oversized")
    if _parse_asset(asset._source_bytes) != asset:
        raise ValueError("asset content does not match its source revision")
