"""In-memory transport for tests and Robo Puppeteer development."""

from __future__ import annotations


class MemoryTransport:
    def __init__(self) -> None:
        self.frames: list[bytes] = []
        self.connected = False

    async def connect(self) -> None:
        self.connected = True

    async def send(self, frame: bytes) -> None:
        if not self.connected:
            raise RuntimeError("transport is not connected")
        self.frames.append(frame)

    async def close(self) -> None:
        self.connected = False
