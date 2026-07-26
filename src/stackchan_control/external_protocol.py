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
    serialized = json.dumps(payload, separators=(",", ":"))
    return identifier, (PREFIX + serialized + "\n").encode()


def decode_event_line(line: str | bytes) -> ExternalEvent | None:
    text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
    text = text.strip()
    if not text.startswith(PREFIX):
        return None
    try:
        value = json.loads(text[len(PREFIX) :])
    except json.JSONDecodeError as exc:
        raise ExternalProtocolError("invalid JSON event") from exc
    if not isinstance(value, dict):
        raise ExternalProtocolError("event line must contain an object")
    event = value.get("event")
    if not isinstance(event, str):
        raise ExternalProtocolError("event line must contain an event string")
    result = value.get("result")
    if result is not None and not isinstance(result, dict):
        raise ExternalProtocolError("result must be an object")
    command_id = value.get("id")
    detail = value.get("detail")
    return ExternalEvent(
        event=event,
        command_id=command_id if isinstance(command_id, str) else None,
        detail=detail if isinstance(detail, str) else None,
        result=result,
    )
