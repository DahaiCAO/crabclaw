from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from loguru import logger
from websockets.server import serve

from crabclaw.dashboard.broadcaster import DashboardBroadcaster


@dataclass
class DashboardConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    http_port: int = 18791
    ws_port: int = 18792


class DashboardServer:
    """Static HTTP + WebSocket streaming server."""

    def __init__(
        self,
        broadcaster: DashboardBroadcaster,
        *,
        static_dir: Path,
        config: DashboardConfig | None = None,
    ) -> None:
        self.broadcaster = broadcaster
        self.static_dir = static_dir
        self.config = config or DashboardConfig()

        self._httpd: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._ws_server: Any | None = None
        self._ws_task: asyncio.Task | None = None

    @property
    def http_url(self) -> str:
        return f"http://{self.config.host}:{self.config.http_port}/"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.config.host}:{self.config.ws_port}/ws"

    def _start_http_in_thread(self) -> None:
        class _Handler(SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A002
                logger.debug("Dashboard HTTP: " + format, *args)

        def _serve() -> None:
            try:
                self._httpd = ThreadingHTTPServer(
                    (self.config.host, self.config.http_port),
                    lambda *a, **kw: _Handler(*a, directory=str(self.static_dir), **kw),
                )
                logger.info("Dashboard HTTP serving {}", self.http_url)
                self._httpd.serve_forever(poll_interval=0.5)
            except Exception as e:
                logger.error("Dashboard HTTP server failed: {}", e)

        self._http_thread = threading.Thread(target=_serve, name="dashboard-http", daemon=True)
        self._http_thread.start()

    async def _ws_loop(self) -> None:
        async def _handler(ws) -> None:
            q = await self.broadcaster.register()
            try:
                await ws.send(json.dumps({"type": "hello", "data": {"ws": self.ws_url}}, ensure_ascii=False))
                while True:
                    msg = await q.get()
                    await ws.send(msg)
            except Exception:
                pass
            finally:
                await self.broadcaster.unregister(q)

        self._ws_server = await serve(_handler, self.config.host, self.config.ws_port)
        logger.info("Dashboard WS serving {}", self.ws_url)
        await self._ws_server.wait_closed()

    async def start(self) -> None:
        if not self.config.enabled:
            logger.info("Dashboard disabled")
            return

        # Fail fast if ports are not available.
        for port in (self.config.http_port, self.config.ws_port):
            with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind((self.config.host, port))
                except OSError as e:
                    raise OSError(f"Dashboard port {port} is not available: {e}") from e

        self._start_http_in_thread()
        self._ws_task = asyncio.create_task(self._ws_loop())

    async def stop(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
            with contextlib.suppress(BaseException):
                await self._ws_task
            self._ws_task = None

        if self._ws_server:
            with contextlib.suppress(BaseException):
                self._ws_server.close()
            self._ws_server = None

        if self._httpd:
            with contextlib.suppress(BaseException):
                self._httpd.shutdown()
                self._httpd.server_close()
            self._httpd = None

