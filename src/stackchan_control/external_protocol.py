"""AgenticForge local external-control protocol used by modified firmware."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final
from uuid import uuid4

PREFIX: Final = "@AF "


class ExternalProtocolError(ValueError):
    """Raised when a local external-control line is malformed."""


@dataclass(frozen=True, slots=True)
class ExternalEvent:
    event: str
    command_id: str | None = None
    detail: str | None = None
    result: dict[str, Any] | None = None


def encode_command(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    command_id: str | None = None,
) -> tuple[str, bytes]:
    if not method:
        raise ValueError("method must not be empty")
    identifier = command_id or uuid4().hex
    payload = {
        "id": identifier,
        "method": method,
        "params": params or {},
    }
    return identifier, (PREFIX + json.dumps(payload, separators=(",", ":")) + "\n").encode()


def decode_event_line(line: str | bytes) -> ExternalEvent | None:
    if isinstance(line, bytes):
        text = line.decode("utf-8", errors="replace")
    else:
        text = line
    text = text.strip()
    if not text.startswith(PREFIX):
        return None
    try:
        value = json.loads(text[len(PREFIX) :])
    except json.JSONDecodeError as exc:
        raise ExternalProtocolError("invalid JSON event") from exc
    if not isinstance(value, dict) or not isinstance(value.get("event"), str):
        raise ExternalProtocolError("event line must contain an event string")
    result = value.get("result")
    if result is not None and not isinstance(result, dict):
        raise ExternalProtocolError("result must be an object")
    return ExternalEvent(
        event=value["event"],
        command_id=value.get("id") if isinstance(value.get("id"), str) else None,
        detail=value.get("detail") if isinstance(value.get("detail"), str) else None,
        result=result,
    )
