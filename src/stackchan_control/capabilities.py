"""Static, versioned schemas for supported USB external-control operations.

Schemas describe wire payloads, not permission or current device limits. A live
firmware capability response must still be intersected with this allowlist.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

SCHEMA_VERSION = "stackchan-external-control-v1"


def _integer(low: int, high: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": low, "maximum": high}


def _object(properties: dict[str, Any], *, minimum: int = 0) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
        "minProperties": minimum,
    }


def _feature() -> dict[str, Any]:
    schema = _object(
        {
            "x": _integer(-100, 100),
            "y": _integer(-100, 100),
            "size": _integer(-100, 100),
            "rotation": _integer(0, 3600),
            "weight": _integer(0, 100),
        },
        minimum=1,
    )
    schema["dependentRequired"] = {"x": ["y"], "y": ["x"]}
    return schema


def _servo(low: int, high: int) -> dict[str, Any]:
    schema = _object({"angle": _integer(low, high), "speed": _integer(0, 1000)})
    schema["required"] = ["angle", "speed"]
    return schema


_COLOR = {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"}
_DURATION = {"type": "number", "minimum": 0, "maximum": 10}
_SCHEMAS: dict[str, dict[str, Any]] = {
    "avatar.update": _object(
        {"leftEye": _feature(), "rightEye": _feature(), "mouth": _feature()}, minimum=1
    ),
    "motion.update.position_only": _object(
        {"yawServo": _servo(-1280, 1280), "pitchServo": _servo(30, 870)}, minimum=1
    ),
    "lights.update": _object(
        {
            "leftRgbColor": _COLOR,
            "rightRgbColor": _COLOR,
            "leftRgbDuration": _DURATION,
            "rightRgbDuration": _DURATION,
        },
        minimum=1,
    ),
    "external_lights.update": {
        **_object(
            {
                "pixels": {"type": "array", "minItems": 37, "maxItems": 37, "items": _COLOR},
                "brightness": _integer(0, 32),
            }
        ),
        "required": ["pixels", "brightness"],
    },
    "system.state": _object({}),
    "system.stop": _object({}),
}


def capability_schema(capability_id: str) -> dict[str, Any]:
    """Return an isolated schema copy; changing it cannot modify the registry."""
    return deepcopy(_SCHEMAS[capability_id])
