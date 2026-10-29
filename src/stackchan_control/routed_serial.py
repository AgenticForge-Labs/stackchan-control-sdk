"""Concurrent request routing for the external-control serial protocol.

This transport is distinct from the stock Avatar packet API. A single reader owns
all reads; each command retains its own events even when another caller is waiting.
No reconnect or command retry is attempted after a transport failure.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Any, Protocol

from .external_protocol import ExternalEvent, decode_event_line, encode_command


class SerialWire(Protocol):
    def write(self, data: bytes) -> int: ...
    def readline(self) -> bytes: ...
    def close(self) -> None: ...


class RoutedSerialError(RuntimeError):
    """A command or the underlying connection failed."""


class UnknownOutcome(RoutedSerialError):
    """The caller cannot establish the device outcome; never automatically retry."""


class RoutedSerialClient:
    """Own an already-open wire with a finite read timeout.

    Events remain available after a timeout so the caller can reconcile a late
    terminal event. Construct a new client explicitly after a disconnect; it
    cannot infer the outcome of commands sent on the old connection.
    """

    def __init__(self, wire: SerialWire) -> None:
        self._wire = wire
        self._condition = threading.Condition()
        self._write_lock = threading.Lock()
        self._events: dict[str, list[ExternalEvent]] = {}
        self._failure: str | None = None
        self._closed = False
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    @classmethod
    def open(
        cls,
        port: str,
        *,
        baudrate: int = 115200,
        read_timeout: float = 0.1,
        write_timeout: float = 0.25,
    ) -> RoutedSerialClient:
        if not math.isfinite(read_timeout) or read_timeout <= 0:
            raise ValueError("read_timeout must be positive and finite")
        if not math.isfinite(write_timeout) or write_timeout <= 0:
            raise ValueError("write_timeout must be positive and finite")
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install stackchan-control[serial] to use USB control") from exc
        return cls(serial.Serial(port, baudrate, timeout=read_timeout, write_timeout=write_timeout))

    def _read_loop(self) -> None:
        try:
            while True:
                with self._condition:
                    if self._closed:
                        return
                line = self._wire.readline()
                if not line:
                    continue
                event = decode_event_line(line)
                if event is None or event.command_id is None:
                    continue
                with self._condition:
                    if event.command_id in self._events:
                        self._events[event.command_id].append(event)
                        self._condition.notify_all()
        except Exception as exc:
            with self._condition:
                if not self._closed:
                    self._failure = f"{type(exc).__name__}: {exc}"
                self._condition.notify_all()

    def submit(self, method: str, params: dict[str, Any] | None = None) -> str:
        command_id, payload = encode_command(method, params)
        with self._write_lock:
            with self._condition:
                self._ensure_open()
                self._events[command_id] = []
            try:
                written = self._wire.write(payload)
                if written != len(payload):
                    raise OSError("incomplete serial write")
            except Exception as exc:
                with self._condition:
                    self._failure = f"{type(exc).__name__}: {exc}"
                    self._condition.notify_all()
                raise UnknownOutcome(
                    f"serial write failed for {command_id}; outcome unknown"
                ) from exc
        return command_id

    def _ensure_open(self) -> None:
        if self._closed or self._failure is not None:
            raise RoutedSerialError(f"serial connection unavailable: {self._failure or 'closed'}")

    def events(self, command_id: str) -> tuple[ExternalEvent, ...]:
        with self._condition:
            if command_id not in self._events:
                raise KeyError(command_id)
            return tuple(self._events[command_id])

    def wait(self, command_id: str, *, timeout: float = 8.0) -> tuple[ExternalEvent, ...]:
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("timeout must be finite and non-negative")
        deadline = time.monotonic() + timeout
        with self._condition:
            if command_id not in self._events:
                raise KeyError(command_id)
            while True:
                events = self._events[command_id]
                if events and events[-1].event in {"completed", "failed", "cancelled"}:
                    return tuple(events)
                if self._closed or self._failure is not None:
                    raise UnknownOutcome(f"connection lost for {command_id}; outcome unknown")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise UnknownOutcome(f"timeout for {command_id}; outcome unknown")
                self._condition.wait(remaining)

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._condition.notify_all()
        self._wire.close()
        self._reader.join(timeout=1)
