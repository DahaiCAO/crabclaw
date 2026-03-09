from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass(frozen=True)
class DashboardEvent:
    type: str
    data: dict[str, Any]

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "data": self.data}, ensure_ascii=False)


class DashboardBroadcaster:
    """In-process event hub for dashboard WebSocket clients."""

    def __init__(self) -> None:
        self._clients: set["asyncio.Queue[str]"] = set()
        self._lock = asyncio.Lock()

    async def register(self) -> "asyncio.Queue[str]":
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._clients.add(q)
        return q

    async def unregister(self, q: "asyncio.Queue[str]") -> None:
        async with self._lock:
            self._clients.discard(q)

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        event = DashboardEvent(type=event_type, data=data).to_json()
        async with self._lock:
            clients = list(self._clients)

        dropped = 0
        for q in clients:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dropped += 1
        if dropped:
            logger.debug("Dashboard: dropped {} events (slow clients)", dropped)

