"""Transport contracts."""

from __future__ import annotations

from typing import Protocol


class Transport(Protocol):
    """Minimal asynchronous binary transport used by the SDK."""

    async def connect(self) -> None: ...

    async def send(self, frame: bytes) -> None: ...

    async def close(self) -> None: ...
