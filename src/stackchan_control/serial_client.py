"""Synchronous USB serial client for the external-control firmware extension."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from .external_protocol import ExternalEvent, decode_event_line, encode_command


class SerialControlError(RuntimeError):
    """Raised when the firmware rejects, cancels, or does not answer a command."""


def candidate_ports() -> list[dict[str, str | bool | None]]:
    try:
        from serial.tools import list_ports
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "Install stackchan-control[serial] to inspect serial ports"
        ) from exc

    candidates: list[dict[str, str | bool | None]] = []
    for port in list_ports.comports():
        descriptions = [port.description, port.manufacturer, port.product]
        text = " ".join(filter(None, descriptions)).lower()
        tokens = ("espressif", "m5stack", "usb jtag", "usb serial")
        likely = any(token in text for token in tokens)
        candidates.append(
            {
                "device": port.device,
                "description": port.description,
                "manufacturer": port.manufacturer,
                "serial_number": port.serial_number,
                "likely_stackchan": likely,
            }
        )
    return candidates


class SerialControlClient:
    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115200,
        timeout: float = 0.1,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Any | None = None

    def __enter__(self) -> SerialControlClient:
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def open(self) -> None:
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Install stackchan-control[serial] to use hardware probing"
            ) from exc
        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        self._serial.reset_input_buffer()

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 8.0,
    ) -> list[ExternalEvent]:
        if self._serial is None:
            raise SerialControlError("serial client is not open")
        command_id, payload = encode_command(method, params)
        self._serial.write(payload)
        self._serial.flush()

        events: list[ExternalEvent] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                continue
            event = decode_event_line(raw)
            if event is None or event.command_id != command_id:
                continue
            events.append(event)
            if event.event in {"failed", "cancelled"}:
                raise SerialControlError(event.detail or f"{method} {event.event}")
            if event.event == "completed":
                return events
        rendered = [asdict(event) for event in events]
        raise SerialControlError(f"timeout waiting for {method}; received {rendered}")
