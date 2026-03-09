from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from crabclaw.dashboard.broadcaster import DashboardBroadcaster


class JsonlTailer:
    """Tail a JSONL file and publish decoded events.

    Designed for audit.log.jsonl (each line is a JSON object).
    """

    def __init__(
        self,
        path: Path,
        broadcaster: DashboardBroadcaster,
        *,
        event_type: str = "audit",
        poll_interval_s: float = 0.5,
        from_end: bool = False,
        max_line_bytes: int = 1024 * 256,
    ) -> None:
        self.path = path
        self.broadcaster = broadcaster
        self.event_type = event_type
        self.poll_interval_s = poll_interval_s
        self.from_end = from_end
        self.max_line_bytes = max_line_bytes

        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except BaseException:
                pass
            self._task = None

    async def _loop(self) -> None:
        pos = 0
        if self.from_end and self.path.exists():
            try:
                pos = self.path.stat().st_size
            except Exception:
                pos = 0

        while self._running:
            try:
                if not self.path.exists():
                    await asyncio.sleep(self.poll_interval_s)
                    continue

                size = self.path.stat().st_size
                if size < pos:
                    # rotation/truncate
                    pos = 0

                if size == pos:
                    await asyncio.sleep(self.poll_interval_s)
                    continue

                # Read incrementally; tolerate partial line at end.
                with self.path.open("rb") as f:
                    f.seek(pos)
                    chunk = f.read(size - pos)
                    pos = f.tell()

                if not chunk:
                    await asyncio.sleep(self.poll_interval_s)
                    continue

                lines = chunk.splitlines()
                # If file does not end with newline, last line may be partial; keep pos back.
                if chunk and not chunk.endswith(b"\n") and lines:
                    partial = lines.pop()
                    pos -= len(partial)

                for raw in lines:
                    if not raw:
                        continue
                    if len(raw) > self.max_line_bytes:
                        continue
                    try:
                        obj = json.loads(raw.decode("utf-8", errors="replace"))
                        if isinstance(obj, dict):
                            await self.broadcaster.publish(self.event_type, obj)
                        else:
                            await self.broadcaster.publish(self.event_type, {"value": obj})
                    except Exception:
                        continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("JsonlTailer error: {}", e)
                await asyncio.sleep(self.poll_interval_s)

