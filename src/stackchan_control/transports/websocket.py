"""Generic WebSocket transport for a compatible relay or future local firmware.

This transport does not implement M5Stack cloud authentication. The stock robot
connects outward to M5Stack's relay, so a local endpoint or compatible relay is
still required before this can control unmodified stock firmware.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast


class _WebSocketConnection(Protocol):
    async def send(self, message: bytes) -> None: ...

    async def close(self) -> None: ...


class WebSocketTransport:
    def __init__(self, url: str, *, additional_headers: Mapping[str, str] | None = None) -> None:
        self.url = url
        self.additional_headers = dict(additional_headers or {})
        self._socket: _WebSocketConnection | None = None

    async def connect(self) -> None:
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError(
                "Install stackchan-control[websocket] to use WebSocketTransport"
            ) from exc
        connection = await connect(self.url, additional_headers=self.additional_headers)
        self._socket = cast(_WebSocketConnection, connection)

    async def send(self, frame: bytes) -> None:
        if self._socket is None:
            raise RuntimeError("transport is not connected")
        await self._socket.send(frame)

    async def close(self) -> None:
        if self._socket is not None:
            await self._socket.close()
            self._socket = None
